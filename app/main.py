"""
Event Stream Engine - Flask Application Factory for the Flask application with Celery integration
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from celery import Celery
import os

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Load configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', '0') == '1'
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://dev_user:dev_password@db:5432/event_stream_dev')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Import models after db is initialized
    with app.app_context():
        from app.core import data_model

    # Register API blueprints
    from app.api.v1.public_api import api_v1
    app.register_blueprint(api_v1)

    # Basic health check route
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'event-stream-engine'}, 200
    
    @app.route('/')
    def index():
        return {
            'message': 'Event Stream Engine API',
            'version': '1.0.0',
            'status': 'ready'
        }, 200
    
    @app.route('/webhooks/inbound', methods=['POST'])
    def inbound_webhook():
        """Fast inbound webhook handler - immediate raw persistence only"""
        from flask import request
        from app.core.data_model import InboundEvent, User, ConsentState
        import uuid
        
        try:
            # Extract raw webhook data (form-encoded for Twilio)
            raw_data = dict(request.form) if request.form else dict(request.get_json() or {})
            
            # Extract channel type and normalize phone number
            from app.core.data_model import extract_channel_and_phone
            raw_phone = raw_data.get('From', '')
            channel_type, normalized_phone = extract_channel_and_phone(raw_phone)
            
            # Data quality check - reject if phone cannot be normalized
            if not normalized_phone:
                print(f"Invalid phone format: {raw_phone}")
                return """<?xml version="1.0" encoding="UTF-8"?>
<Response></Response>""", 200, {'Content-Type': 'text/xml'}
                
            # Immediate raw persistence for audit trail
            event = InboundEvent(
                id=str(uuid.uuid4()),
                raw_payload=raw_data,
                message_sid=raw_data.get('MessageSid'),
                from_phone=normalized_phone,
                channel_type=channel_type,
                normalized_body=raw_data.get('Body', '').lower().strip() if raw_data.get('Body') else None
            )
            
            db.session.add(event)
            
            # Fast STOP command handling (critical for compliance)
            message_body = raw_data.get('Body', '').lower().strip()
            
            if message_body in ['stop', 'stopall', 'unsubscribe', 'cancel', 'end', 'quit'] and normalized_phone:
                user = User.query.get(normalized_phone)
                if user:
                    user.consent_state = ConsentState.STOP
                    user.updated_at = db.func.now()
                else:
                    # Create user with STOP state if not exists
                    user = User(
                        phone_e164=normalized_phone,
                        consent_state=ConsentState.STOP,
                        attributes={}
                    )
                    db.session.add(user)
            
            db.session.commit()
            
            # Queue async processing task (skip for now to avoid import errors)
            # from app.tasks.webhook_processor import process_inbound_message
            # process_inbound_message.delay(event.id)
            print(f"Stored inbound event: {event.id}")
            
            # Return TwiML response
            return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Message received</Message>
</Response>""", 200, {'Content-Type': 'text/xml'}
            
        except Exception as e:
            db.session.rollback()
            print(f"Inbound webhook error: {e}")
            # Still return success to Twilio to avoid retries
            return """<?xml version="1.0" encoding="UTF-8"?>
<Response></Response>""", 200, {'Content-Type': 'text/xml'}
    
    @app.route('/webhooks/status', methods=['POST'])
    def status_webhook():
        """Fast status callback handler - immediate raw persistence only"""
        from flask import request
        from app.core.data_model import DeliveryReceipt, Message
        import uuid
        
        try:
            # Extract raw callback data
            raw_data = dict(request.form) if request.form else dict(request.get_json() or {})
            
            # Immediate raw persistence
            receipt = DeliveryReceipt(
                id=str(uuid.uuid4()),
                raw_payload=raw_data,
                message_sid=raw_data.get('MessageSid'),
                message_status=raw_data.get('MessageStatus'),
                error_code=int(raw_data.get('ErrorCode')) if raw_data.get('ErrorCode') else None
            )
            
            db.session.add(receipt)
            db.session.commit()
            
            # Queue async processing task (skip for now to avoid import errors)
            # from app.tasks.webhook_processor import process_status_callback
            # process_status_callback.delay(receipt.id)
            print(f"Stored delivery receipt: {receipt.id}")
            
            return {'status': 'received'}, 200
            
        except Exception as e:
            db.session.rollback()
            print(f"Status webhook error: {e}")
            return {'status': 'error'}, 500
    
    return app


def create_celery(app=None):
    """Create and configure Celery instance"""
    celery = Celery(
        'event-stream-engine',
        broker=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
        backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
    )
    
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
    from app.runner import tasks
    from app.tasks import webhook_processor
except ImportError:
    # Tasks modules may not exist in all environments
    pass


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)