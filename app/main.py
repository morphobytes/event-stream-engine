"""
Event Stream Engine - Flask Application Factory with Celery integration

This module provides the main Flask application factory and Celery configuration
for the Event Stream Engine, a production-grade event-driven messaging platform.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from celery import Celery
import os
import logging
import sys
from dotenv import load_dotenv

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()


def configure_logging(app: Flask) -> None:
    """Configure cloud-native logging for production deployment

    Configures logging to write to stdout/stderr for Cloud Run compatibility
    and proper log ingestion by Google Cloud Logging.

    Args:
        app: Flask application instance
    """
    # Set logging level based on environment
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )

    # Configure Flask app logger
    app.logger.setLevel(log_level)

    # Configure SQLAlchemy logging (reduce verbosity in production)
    if not app.config.get("DEBUG"):
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    app.logger.info("Event Stream Engine logging configured")


def validate_environment_config(app: Flask) -> None:
    """Validate that all required environment variables are properly loaded
    
    Args:
        app: Flask application instance
    
    Raises:
        ValueError: If critical environment variables are missing
    """
    required_vars = {
        "SECRET_KEY": "Flask secret key for session security",
        "DATABASE_URL": "PostgreSQL database connection string", 
        "REDIS_URL": "Redis connection string for Celery broker"
    }
    
    missing_vars = []
    for var_name, description in required_vars.items():
        if not os.getenv(var_name):
            missing_vars.append(f"{var_name} ({description})")
    
    if missing_vars:
        error_msg = f"Missing required environment variables:\n" + "\n".join(f"- {var}" for var in missing_vars)
        app.logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Warn about recommended but optional variables
    optional_vars = {
        "TWILIO_ACCOUNT_SID": "Twilio Account SID for WhatsApp messaging",
        "TWILIO_AUTH_TOKEN": "Twilio Auth Token for API access", 
        "TWILIO_PHONE_NUMBER": "Twilio WhatsApp phone number"
    }
    
    missing_optional = []
    for var_name, description in optional_vars.items():
        if not os.getenv(var_name):
            missing_optional.append(f"{var_name} ({description})")
    
    if missing_optional:
        warning_msg = "Missing optional environment variables (Twilio features will be disabled):\n" + "\n".join(f"- {var}" for var in missing_optional)
        app.logger.warning(warning_msg)
    
    app.logger.info("Environment configuration validation completed")


def create_app() -> Flask:
    """Create and configure Flask application

    Returns:
        Flask: Configured Flask application instance
    """
    # Load environment variables from .env file (for local development only)
    # In production (Cloud Run), environment variables are set by the platform
    # Docker Compose uses env_file directive, so load_dotenv() is backup
    if not os.getenv('GOOGLE_CLOUD_PROJECT'):  # Skip in production
        load_dotenv()
    
    app = Flask(__name__)

    # Load configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "0") == "1"

    # Database configuration
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "postgresql://dev_user:dev_password@db:5432/event_stream_dev"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Redis configuration for Celery and caching
    app.config["REDIS_URL"] = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # Validate environment configuration
    validate_environment_config(app)
    
    # Configure logging for cloud-native deployment
    configure_logging(app)

    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models to ensure they're registered with SQLAlchemy for migrations
    from app.core import data_model

    # Add custom template filters
    @app.template_filter('tojsonpretty')
    def to_json_pretty(value):
        """Convert dict to pretty JSON string for template display"""
        import json
        try:
            return json.dumps(value, indent=2, ensure_ascii=False)
        except:
            return str(value)

    # Register API blueprints
    from app.api.v1.public_api import api_v1

    app.register_blueprint(api_v1)

    # Register UI blueprint
    from app.ui_routes import ui

    app.register_blueprint(ui)

    # Basic health check route
    @app.route("/health")
    def health_check():
        return {"status": "healthy", "service": "event-stream-engine"}, 200

    # Root route handled by UI blueprint

    @app.route("/webhooks/inbound", methods=["POST"])
    def inbound_webhook():
        """Fast inbound webhook handler - immediate raw persistence only"""
        from flask import request
        from app.core.data_model import InboundEvent, User, ConsentState
        import uuid

        try:
            # Extract raw webhook data (form-encoded for Twilio)
            raw_data = (
                dict(request.form) if request.form else dict(request.get_json() or {})
            )

            # Extract channel type and normalize phone number
            from app.core.data_model import extract_channel_and_phone

            raw_phone = raw_data.get("From", "")
            channel_type, normalized_phone = extract_channel_and_phone(raw_phone)

            # Data quality check - reject if phone cannot be normalized
            if not normalized_phone:
                app.logger.warning(f"Invalid phone format received: {raw_phone}")
                return (
                    """<?xml version="1.0" encoding="UTF-8"?>
<Response></Response>""",
                    200,
                    {"Content-Type": "text/xml"},
                )

            # Immediate raw persistence for audit trail
            event = InboundEvent(
                id=str(uuid.uuid4()),
                raw_payload=raw_data,
                message_sid=raw_data.get("MessageSid"),
                from_phone=normalized_phone,
                channel_type=channel_type,
                normalized_body=(
                    raw_data.get("Body", "").lower().strip()
                    if raw_data.get("Body")
                    else None
                ),
            )

            db.session.add(event)

            # Fast STOP command handling (critical for compliance)
            message_body = raw_data.get("Body", "").lower().strip()

            if (
                message_body
                in ["stop", "stopall", "unsubscribe", "cancel", "end", "quit"]
                and normalized_phone
            ):
                user = User.query.get(normalized_phone)
                if user:
                    user.consent_state = ConsentState.STOP
                    user.updated_at = db.func.now()
                else:
                    # Create user with STOP state if not exists
                    user = User(
                        phone_number=normalized_phone,
                        consent_state=ConsentState.STOP,
                        attributes={},
                    )
                    db.session.add(user)

            db.session.commit()

            # Audit logging for compliance
            app.logger.info(
                f"Inbound event stored: {event.id} from {normalized_phone} "
                f"(MessageSid: {event.message_sid})"
            )

            # Queue async processing task (skip for now to avoid import errors)
            # from app.tasks.webhook_processor import process_inbound_message
            # process_inbound_message.delay(event.id)

            # Return TwiML response
            return (
                """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Message received</Message>
</Response>""",
                200,
                {"Content-Type": "text/xml"},
            )

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Inbound webhook error: {e}", exc_info=True)
            # Still return success to Twilio to avoid retries
            return (
                """<?xml version="1.0" encoding="UTF-8"?>
<Response></Response>""",
                200,
                {"Content-Type": "text/xml"},
            )

    @app.route("/webhooks/status", methods=["POST"])
    def status_webhook():
        """Fast status callback handler - immediate raw persistence only"""
        from flask import request
        from app.core.data_model import DeliveryReceipt
        import uuid

        try:
            # Extract raw callback data
            raw_data = (
                dict(request.form) if request.form else dict(request.get_json() or {})
            )

            # Immediate raw persistence
            receipt = DeliveryReceipt(
                id=str(uuid.uuid4()),
                raw_payload=raw_data,
                message_sid=raw_data.get("MessageSid"),
                message_status=raw_data.get("MessageStatus"),
                error_code=(
                    int(raw_data.get("ErrorCode"))
                    if raw_data.get("ErrorCode")
                    else None
                ),
            )

            db.session.add(receipt)
            db.session.commit()

            # Audit logging for compliance
            app.logger.info(
                f"Delivery receipt stored: {receipt.id} "
                f"(MessageSid: {receipt.message_sid}, Status: {receipt.message_status})"
            )

            # Queue async processing task (skip for now to avoid import errors)
            # from app.tasks.webhook_processor import process_status_callback
            # process_status_callback.delay(receipt.id)

            return {"status": "received"}, 200

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Status webhook error: {e}", exc_info=True)
            return {"status": "error"}, 500

    return app


def create_celery(app: Flask = None) -> Celery:
    """Create and configure Celery instance with Beat scheduler

    Args:
        app: Flask application instance for context binding

    Returns:
        Celery: Configured Celery instance with Beat scheduler
    """
    # Ensure .env is loaded for Celery workers too (local development only)
    if not os.getenv('GOOGLE_CLOUD_PROJECT'):  # Skip in production
        load_dotenv()
    
    celery = Celery(
        "event-stream-engine",
        broker=os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://redis:6379/0")),
        backend=os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://redis:6379/0")),
    )

    # Configure Celery Beat for scheduled tasks
    celery.conf.beat_schedule = {
        "check-scheduled-campaigns": {
            "task": "app.runner.tasks.check_scheduled_campaigns",
            "schedule": 30.0,  # Run every 30 seconds
        },
        "cleanup-old-rate-limits": {
            "task": "app.runner.tasks.cleanup_old_rate_limits",
            "schedule": 300.0,  # Run every 5 minutes
        },
    }
    celery.conf.timezone = "UTC"

    if app:
        # Initialize Celery with Flask app context
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    return celery


# Create Flask app instance
app = create_app()

# Create Celery instance
celery_app = create_celery(app)

# Import tasks to register them with Celery
try:
    from app.runner import (
        tasks,
    )  # This will load all tasks including campaign orchestration
    from app.tasks import webhook_processor
except ImportError:
    # Tasks modules may not exist in all environments
    pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
