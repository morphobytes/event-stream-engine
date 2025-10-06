"""
Public API v1 - REST endpoints for Event Stream Engine
Implements CRUD operations for Users, Campaigns, Segments, and Triggers
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError
import os
import uuid
from typing import Dict, Any, Tuple
from werkzeug.utils import secure_filename
from app.main import db
from app.core.data_model import (
    User,
    Campaign,
    Template,
    Segment,
    Message,
    DeliveryReceipt,
    InboundEvent,
    ConsentState,
)
from app.api.v1.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse,
    SegmentCreate,
    SegmentResponse,
    TemplateResponse,
    CampaignTriggerRequest,
    CampaignTriggerResponse,
    ErrorResponse,
    ValidationErrorResponse,
    HealthResponse,
    CampaignStatusEnum,
    MessageStatusResponse,
    CampaignSummaryStats,
    ReportingDashboardResponse,
)
from datetime import datetime, timedelta
from sqlalchemy import func, desc, case

# Create API Blueprint
api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


# Helper functions
def sqlalchemy_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert SQLAlchemy model to dict with enum conversion

    Args:
        obj: SQLAlchemy model instance

    Returns:
        Dict[str, Any]: Dictionary representation of the model
    """
    result = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        # Convert enum values to strings
        if hasattr(value, "value"):
            result[column.name] = value.value
        else:
            result[column.name] = value
    return result


def handle_validation_error(error: ValidationError) -> Tuple[Any, int]:
    """Handle Pydantic validation errors

    Args:
        error: Pydantic validation error

    Returns:
        Tuple[Any, int]: JSON response and HTTP status code
    """
    return (
        jsonify(
            ValidationErrorResponse(
                message="Invalid input data",
                field_errors=(
                    error.errors()
                    if hasattr(error, "errors")
                    else {"general": [str(error)]}
                ),
            ).dict()
        ),
        400,
    )


def handle_integrity_error(error):
    """Handle database integrity errors"""
    return (
        jsonify(
            {
                "error": "Database Error",
                "message": "Data integrity constraint violated",
                "details": str(error.orig) if hasattr(error, "orig") else str(error),
            }
        ),
        409,
    )


def handle_not_found(resource_type, identifier):
    """Handle resource not found errors"""
    return (
        jsonify(
            {
                "error": "Not Found",
                "message": f"{resource_type} with identifier {identifier} not found",
            }
        ),
        404,
    )


# USERS ENDPOINTS
@api_v1.route("/users", methods=["GET"])
def get_users():
    """
    Get paginated list of users with filtering
    Query params: page, per_page, consent_state, topic
    """
    try:
        # Pagination parameters
        page = request.args.get("page", 1, type=int)
        per_page = min(
            request.args.get("per_page", 20, type=int), 100
        )  # Max 100 per page

        # Build query with filters
        query = User.query

        # Filter by consent state
        consent_state = request.args.get("consent_state")
        if consent_state:
            try:
                consent_enum = ConsentState(consent_state.upper())
                query = query.filter(User.consent_state == consent_enum)
            except ValueError:
                return (
                    jsonify(
                        ErrorResponse(
                            error="Invalid Parameter", message="Invalid consent state"
                        ).dict()
                    ),
                    400,
                )

        # Filter by subscription topic
        topic = request.args.get("topic")
        if topic:
            query = query.join(User.subscriptions).filter_by(topic=topic)

        # Execute paginated query
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        # Convert to Pydantic models with enum handling
        user_responses = []
        for user in paginated.items:
            user_dict = sqlalchemy_to_dict(user)
            user_responses.append(UserResponse.model_validate(user_dict))

        # Create response
        result = UserListResponse(
            users=user_responses,
            total=paginated.total,
            page=page,
            per_page=per_page,
            has_next=paginated.has_next,
            has_prev=paginated.has_prev,
            pages=paginated.pages,
        )

        return jsonify(result.dict()), 200

    except Exception as e:
        return (
            jsonify(
                ErrorResponse(error="Internal Server Error", message=str(e)).dict()
            ),
            500,
        )


@api_v1.route("/users", methods=["POST"])
def create_user():
    """Create a new user with E.164 validation"""
    try:
        # Validate and deserialize input
        user_data = UserCreate(**request.json)

        # Check if user already exists
        existing_user = User.query.get(user_data.phone_e164)
        if existing_user:
            return (
                jsonify(
                    ErrorResponse(
                        error="Conflict",
                        message=(
                            f"User with phone {user_data.phone_e164} already exists"
                        ),
                    ).dict()
                ),
                409,
            )

        # Create new user
        new_user = User(
            phone_e164=user_data.phone_e164,
            attributes=user_data.attributes,
            consent_state=ConsentState(user_data.consent_state.value),
        )

        db.session.add(new_user)
        db.session.commit()

        user_dict = sqlalchemy_to_dict(new_user)
        return jsonify(UserResponse.model_validate(user_dict).model_dump()), 201

    except ValidationError as e:
        return handle_validation_error(e)
    except IntegrityError as e:
        db.session.rollback()
        return handle_integrity_error(e)
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                ErrorResponse(error="Internal Server Error", message=str(e)).dict()
            ),
            500,
        )


@api_v1.route("/users/<phone_e164>", methods=["PUT"])
def update_user(phone_e164):
    """Update user attributes or consent state"""
    try:
        # Find user
        user = User.query.get(phone_e164)
        if not user:
            return handle_not_found("User", phone_e164)

        # Validate input (partial update allowed)
        update_data = UserUpdate(**request.json)

        # Update fields
        if update_data.attributes is not None:
            user.attributes = update_data.attributes

        if update_data.consent_state is not None:
            user.consent_state = ConsentState(update_data.consent_state.value)

        user.updated_at = datetime.utcnow()

        db.session.commit()

        user_dict = sqlalchemy_to_dict(user)
        return jsonify(UserResponse.model_validate(user_dict).model_dump()), 200

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                ErrorResponse(error="Internal Server Error", message=str(e)).dict()
            ),
            500,
        )


# SEGMENTS ENDPOINTS
@api_v1.route("/segments", methods=["GET"])
def get_segments():
    """Get all segment definitions"""
    try:
        segments = Segment.query.all()
        segment_responses = [SegmentResponse.from_orm(segment) for segment in segments]
        return jsonify({"segments": [s.dict() for s in segment_responses]}), 200
    except Exception as e:
        return (
            jsonify(
                ErrorResponse(error="Internal Server Error", message=str(e)).dict()
            ),
            500,
        )


@api_v1.route("/segments", methods=["POST"])
def create_segment():
    """Create a new segment definition"""
    try:
        # Validate and deserialize input
        segment_data = SegmentCreate(**request.json)

        # Check for duplicate name
        existing = Segment.query.filter_by(name=segment_data.name).first()
        if existing:
            return (
                jsonify(
                    ErrorResponse(
                        error="Conflict",
                        message=f"Segment with name {segment_data.name} already exists",
                    ).dict()
                ),
                409,
            )

        # Create new segment
        new_segment = Segment(
            name=segment_data.name, definition_json=segment_data.definition_json
        )

        db.session.add(new_segment)
        db.session.commit()

        return jsonify(SegmentResponse.from_orm(new_segment).dict()), 201

    except ValidationError as e:
        return handle_validation_error(e)
    except IntegrityError as e:
        db.session.rollback()
        return handle_integrity_error(e)
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                ErrorResponse(error="Internal Server Error", message=str(e)).dict()
            ),
            500,
        )


# CAMPAIGNS ENDPOINTS
@api_v1.route("/campaigns", methods=["GET"])
def get_campaigns():
    """Get campaigns with status filtering"""
    try:
        # Build query with status filter
        query = Campaign.query

        status_filter = request.args.get("status")
        if status_filter:
            query = query.filter(Campaign.status == status_filter.upper())

        campaigns = query.all()

        # Convert to Pydantic models with template data
        campaign_responses = []
        for campaign in campaigns:
            template_response = (
                TemplateResponse.from_orm(campaign.template)
                if campaign.template
                else None
            )
            campaign_dict = CampaignResponse.from_orm(campaign).dict()
            campaign_dict["template"] = (
                template_response.dict() if template_response else None
            )
            campaign_responses.append(campaign_dict)

        result = CampaignListResponse(
            campaigns=campaign_responses, total=len(campaigns)
        )

        return jsonify(result.dict()), 200

    except Exception as e:
        return (
            jsonify(
                ErrorResponse(error="Internal Server Error", message=str(e)).dict()
            ),
            500,
        )


@api_v1.route("/campaigns", methods=["POST"])
def create_campaign():
    """Create a new campaign"""
    try:
        # Validate and deserialize input
        campaign_data = CampaignCreate(**request.json)

        # Verify template exists
        template = Template.query.get(campaign_data.template_id)
        if not template:
            return handle_not_found("Template", campaign_data.template_id)

        # Create new campaign
        new_campaign = Campaign(
            topic=campaign_data.topic,
            template_id=campaign_data.template_id,
            status=campaign_data.status.value,
            rate_limit_per_second=campaign_data.rate_limit_per_second,
            quiet_hours_start=campaign_data.quiet_hours_start,
            quiet_hours_end=campaign_data.quiet_hours_end,
            schedule_time=campaign_data.schedule_time,
        )

        db.session.add(new_campaign)
        db.session.commit()

        # Load with template relationship
        db.session.refresh(new_campaign)
        response_dict = CampaignResponse.from_orm(new_campaign).dict()
        if new_campaign.template:
            response_dict["template"] = TemplateResponse.from_orm(
                new_campaign.template
            ).dict()

        return jsonify(response_dict), 201

    except ValidationError as e:
        return handle_validation_error(e)
    except IntegrityError as e:
        db.session.rollback()
        return handle_integrity_error(e)
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                ErrorResponse(error="Internal Server Error", message=str(e)).dict()
            ),
            500,
        )


@api_v1.route("/campaigns/<int:campaign_id>", methods=["PUT"])
def update_campaign(campaign_id):
    """Update campaign rules, schedule, or status"""
    try:
        # Find campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return handle_not_found("Campaign", campaign_id)

        # Validate input (partial update allowed)
        update_data = CampaignUpdate(**request.json)

        # Update fields
        if update_data.status is not None:
            campaign.status = update_data.status.value
        if update_data.rate_limit_per_second is not None:
            campaign.rate_limit_per_second = update_data.rate_limit_per_second
        if update_data.quiet_hours_start is not None:
            campaign.quiet_hours_start = update_data.quiet_hours_start
        if update_data.quiet_hours_end is not None:
            campaign.quiet_hours_end = update_data.quiet_hours_end
        if update_data.schedule_time is not None:
            campaign.schedule_time = update_data.schedule_time

        campaign.updated_at = datetime.utcnow()

        db.session.commit()

        # Load with template relationship
        db.session.refresh(campaign)
        response_dict = CampaignResponse.from_orm(campaign).dict()
        if campaign.template:
            response_dict["template"] = TemplateResponse.from_orm(
                campaign.template
            ).dict()

        return jsonify(response_dict), 200

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                ErrorResponse(error="Internal Server Error", message=str(e)).dict()
            ),
            500,
        )


# CAMPAIGN TRIGGER ENDPOINT
@api_v1.route("/campaigns/<int:campaign_id>/trigger", methods=["POST"])
def trigger_campaign(campaign_id):
    """Trigger campaign execution (placeholder for Celery task)"""
    try:
        # Find campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return handle_not_found("Campaign", campaign_id)

        # Validate trigger parameters
        trigger_data = CampaignTriggerRequest(**(request.json or {}))

        # Basic validation
        if campaign.status not in ["READY", "DRAFT"]:
            return (
                jsonify(
                    ErrorResponse(
                        error="Invalid State",
                        message=(
                            f"Campaign must be in READY or DRAFT state to trigger "
                            f"(current: {campaign.status.value})"
                        ),
                    ).dict()
                ),
                400,
            )

        # Verify template exists and is valid
        if not campaign.template:
            return (
                jsonify(
                    ErrorResponse(
                        error="Invalid Configuration",
                        message="Campaign template not found",
                    ).dict()
                ),
                400,
            )

        # Queue campaign execution via orchestrator
        if not trigger_data.dry_run:
            from app.runner.tasks import trigger_campaign_execution

            # Trigger campaign execution
            execution_result = trigger_campaign_execution.delay(campaign_id)

            execution_task_id = execution_result.id
            campaign.status = "RUNNING"
        else:
            execution_task_id = None
            # Dry run - don't change status

        campaign.updated_at = datetime.utcnow()
        db.session.commit()

        response = CampaignTriggerResponse(
            message=(
                "Campaign execution started"
                if not trigger_data.dry_run
                else "Dry run completed"
            ),
            campaign_id=campaign_id,
            status=CampaignStatusEnum(campaign.status),
            task_id=execution_task_id,
            dry_run=trigger_data.dry_run,
            immediate=trigger_data.immediate,
            segment_id=trigger_data.segment_id,
        )

        return jsonify(response.dict()), 200

    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                ErrorResponse(error="Internal Server Error", message=str(e)).dict()
            ),
            500,
        )


# HEALTH CHECK
@api_v1.route("/health", methods=["GET"])
def api_health():
    """API health check endpoint"""
    health_response = HealthResponse(
        status="healthy", version="v1", timestamp=datetime.utcnow().isoformat()
    )
    return jsonify(health_response.dict()), 200


# INGESTION ENDPOINTS
@api_v1.route("/ingest/users/bulk", methods=["POST"])
def bulk_ingest_users_endpoint():
    """
    Bulk user ingestion from CSV/JSON file upload
    Accepts multipart file upload and queues processing task
    """
    try:
        # Validate file upload
        if "file" not in request.files:
            return (
                jsonify(
                    ErrorResponse(
                        error="Bad Request", message="No file provided in request"
                    ).dict()
                ),
                400,
            )

        file = request.files["file"]
        if file.filename == "":
            return (
                jsonify(
                    ErrorResponse(
                        error="Bad Request", message="No file selected"
                    ).dict()
                ),
                400,
            )

        # Validate file type
        allowed_extensions = {"csv", "json", "jsonl"}
        file_extension = (
            file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        )

        if file_extension not in allowed_extensions:
            return (
                jsonify(
                    ErrorResponse(
                        error="Bad Request",
                        message=(
                            f'Unsupported file type. Allowed: {", ".join(allowed_extensions)}'
                        ),
                    ).dict()
                ),
                400,
            )

        # Use existing app uploads directory - app user has full access here
        upload_dir = "/app/uploads"
        os.makedirs(upload_dir, mode=0o755, exist_ok=True)

        # Save file with unique name
        unique_filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)

        # Queue Celery task for processing
        from app.runner.tasks import bulk_ingest_users

        task = bulk_ingest_users.delay(file_path, file_extension)

        return (
            jsonify(
                {
                    "message": "File uploaded successfully, processing started",
                    "task_id": task.id,
                    "file_name": file.filename,
                    "estimated_processing_time": "1-5 minutes depending on file size",
                }
            ),
            202,
        )

    except Exception as e:
        return (
            jsonify(
                ErrorResponse(
                    error="Internal Server Error",
                    message=f"Failed to process upload: {str(e)}",
                ).dict()
            ),
            500,
        )


@api_v1.route("/ingest/triggers", methods=["POST"])
def process_trigger_events_endpoint():
    """
    Process real-time trigger events for campaign execution
    Accepts JSON/JSONL payload with trigger event data
    """
    try:
        # Validate content type
        if not request.is_json:
            return (
                jsonify(
                    ErrorResponse(
                        error="Bad Request",
                        message="Content-Type must be application/json",
                    ).dict()
                ),
                400,
            )

        payload = request.get_json()
        if not payload:
            return (
                jsonify(
                    ErrorResponse(
                        error="Bad Request", message="Empty JSON payload"
                    ).dict()
                ),
                400,
            )

        # Handle both single event and array of events
        events = payload if isinstance(payload, list) else [payload]
        task_ids = []

        # Queue processing task for each event
        from app.runner.tasks import process_trigger_event

        for event in events:
            # Add event ID if not present
            if "event_id" not in event:
                event["event_id"] = str(uuid.uuid4())

            task = process_trigger_event.delay(event)
            task_ids.append({"event_id": event["event_id"], "task_id": task.id})

        return (
            jsonify(
                {
                    "message": (
                        f"Successfully queued {len(events)} trigger event(s) for processing"
                    ),
                    "tasks": task_ids,
                    "processing_status": "queued",
                }
            ),
            202,
        )

    except Exception as e:
        return (
            jsonify(
                ErrorResponse(
                    error="Internal Server Error",
                    message=f"Failed to process trigger events: {str(e)}",
                ).dict()
            ),
            500,
        )


@api_v1.route("/ingest/status/<task_id>", methods=["GET"])
def get_ingestion_task_status(task_id: str):
    """
    Get status of an ingestion task
    Returns task status and results if completed
    """
    try:
        from app.main import celery_app

        # Get task result
        task_result = celery_app.AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": task_result.status,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if task_result.ready():
            if task_result.successful():
                response["result"] = task_result.result
            else:
                response["error"] = str(task_result.info)

        return jsonify(response), 200

    except Exception as e:
        return (
            jsonify(
                ErrorResponse(
                    error="Internal Server Error",
                    message=f"Failed to get task status: {str(e)}",
                ).dict()
            ),
            500,
        )


# ============================================================================
# REPORTING & MONITORING ENDPOINTS (Phase 4.0)
# ============================================================================


@api_v1.route("/messages/<int:message_id>", methods=["GET"])
def get_message_status(message_id):
    """
    Get detailed status of a specific message
    Endpoint: GET /api/v1/messages/{message_id}
    """
    try:
        # Query message with left join to delivery receipt
        message_query = (
            db.session.query(Message, DeliveryReceipt)
            .outerjoin(
                DeliveryReceipt, Message.provider_sid == DeliveryReceipt.message_sid
            )
            .filter(Message.id == message_id)
        )

        result = message_query.first()
        if not result:
            return (
                jsonify(
                    ErrorResponse(
                        error="Not Found", message=f"Message {message_id} not found"
                    ).dict()
                ),
                404,
            )

        message, delivery_receipt = result

        # Build response with delivery information if available
        response_data = {
            "message_id": message.id,
            "user_phone": message.user_phone,
            "campaign_id": message.campaign_id,
            "template_id": message.template_id,
            "rendered_content": message.rendered_content,
            "status": (
                message.status.value
                if hasattr(message.status, "value")
                else str(message.status)
            ),
            "channel": (
                message.channel.value
                if hasattr(message.channel, "value")
                else str(message.channel)
            ),
            "provider_sid": message.provider_sid,
            "sent_at": message.sent_at,
            "error_code": message.error_code,
            "error_message": message.error_message,
            "created_at": message.created_at,
            "delivery_status": (
                delivery_receipt.message_status if delivery_receipt else None
            ),
            "delivered_at": (
                delivery_receipt.received_at
                if delivery_receipt
                and delivery_receipt.message_status in ["delivered", "read"]
                else None
            ),
            "read_at": (
                delivery_receipt.received_at
                if delivery_receipt and delivery_receipt.message_status == "read"
                else None
            ),
        }

        return jsonify(MessageStatusResponse(**response_data).dict()), 200

    except Exception as e:
        return (
            jsonify(
                ErrorResponse(
                    error="Internal Server Error",
                    message=f"Failed to get message status: {str(e)}",
                ).dict()
            ),
            500,
        )


@api_v1.route("/reporting/campaigns/<int:campaign_id>/summary", methods=["GET"])
def get_campaign_summary(campaign_id):
    """
    Get comprehensive campaign execution summary with BI metrics
    Endpoint: GET /api/v1/reporting/campaigns/{campaign_id}/summary
    """
    try:
        # Get campaign info
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return (
                jsonify(
                    ErrorResponse(
                        error="Not Found", message=f"Campaign {campaign_id} not found"
                    ).dict()
                ),
                404,
            )

        # Get message statistics using SQL aggregation
        message_stats = (
            db.session.query(
                func.count(Message.id).label("total_messages"),
                func.sum(func.case((Message.status == "QUEUED", 1), else_=0)).label(
                    "queued"
                ),
                func.sum(func.case((Message.status == "SENT", 1), else_=0)).label(
                    "sent"
                ),
                func.sum(func.case((Message.status == "FAILED", 1), else_=0)).label(
                    "failed"
                ),
            )
            .filter(Message.campaign_id == campaign_id)
            .first()
        )

        # Get delivery statistics from delivery receipts
        delivery_stats = (
            db.session.query(
                func.count(DeliveryReceipt.id).label("total_receipts"),
                func.sum(
                    func.case(
                        (DeliveryReceipt.message_status == "delivered", 1), else_=0
                    )
                ).label("delivered"),
                func.sum(
                    func.case((DeliveryReceipt.message_status == "read", 1), else_=0)
                ).label("read"),
            )
            .join(Message, Message.provider_sid == DeliveryReceipt.message_sid)
            .filter(Message.campaign_id == campaign_id)
            .first()
        )

        # Get error code analysis
        error_analysis = (
            db.session.query(
                Message.error_code,
                Message.error_message,
                func.count(Message.id).label("count"),
            )
            .filter(Message.campaign_id == campaign_id, Message.error_code.isnot(None))
            .group_by(Message.error_code, Message.error_message)
            .order_by(desc(func.count(Message.id)))
            .limit(5)
            .all()
        )

        # Get opt-outs during campaign (users who opted out after campaign started)
        opt_outs_during = (
            db.session.query(func.count(User.phone_e164))
            .filter(
                User.consent_state.in_(["OPT_OUT", "STOP"]),
                (
                    User.updated_at >= campaign.created_at
                    if campaign.created_at
                    else datetime.utcnow()
                ),
            )
            .scalar()
            or 0
        )

        # Calculate metrics
        total_messages = message_stats.total_messages or 0
        sent = message_stats.sent or 0
        delivered = delivery_stats.delivered or 0
        failed = message_stats.failed or 0

        delivery_rate = (delivered / sent * 100) if sent > 0 else 0.0
        success_rate = (
            ((sent - failed) / total_messages * 100) if total_messages > 0 else 0.0
        )

        # Calculate average delivery time
        # (mock calculation - would need timestamp analysis)
        avg_delivery_time = (
            None  # Could calculate from sent_at vs delivery receipt timestamps
        )

        # Format error codes
        top_errors = [
            {
                "error_code": str(error.error_code),
                "error_message": error.error_message or "Unknown error",
                "count": error.count,
            }
            for error in error_analysis
        ]

        response_data = {
            "campaign_id": campaign.id,
            "campaign_topic": campaign.topic,
            "campaign_status": campaign.status,
            "total_recipients": total_messages,
            # Assuming 1 message per recipient for now
            "messages_queued": message_stats.queued or 0,
            "messages_sent": sent,
            "messages_delivered": delivered,
            "messages_failed": failed,
            "opt_outs_during_campaign": opt_outs_during,
            "quiet_hours_skipped": 0,  # Would need task result analysis
            "rate_limit_skipped": 0,  # Would need task result analysis
            "template_errors": 0,  # Would need task result analysis
            "delivery_rate_percent": round(delivery_rate, 2),
            "success_rate_percent": round(success_rate, 2),
            "average_delivery_time_seconds": avg_delivery_time,
            "top_error_codes": top_errors,
            "campaign_started_at": campaign.created_at,
            "campaign_completed_at": (
                campaign.updated_at if campaign.status == "COMPLETED" else None
            ),
            "last_updated": datetime.utcnow(),
        }

        return jsonify(CampaignSummaryStats(**response_data).dict()), 200

    except Exception as e:
        return (
            jsonify(
                ErrorResponse(
                    error="Internal Server Error",
                    message=f"Failed to get campaign summary: {str(e)}",
                ).dict()
            ),
            500,
        )


@api_v1.route("/monitoring/inbound", methods=["GET"])
def get_recent_inbound_events():
    """
    Get recent inbound messages for monitoring dashboard
    Endpoint: GET /api/v1/monitoring/inbound?limit=50&hours=24
    """
    try:
        # Get query parameters
        limit = request.args.get("limit", 50, type=int)
        hours = request.args.get("hours", 24, type=int)

        # Calculate time threshold
        time_threshold = datetime.utcnow() - timedelta(hours=hours)

        # Query recent inbound events
        inbound_events = (
            InboundEvent.query.filter(InboundEvent.processed_at >= time_threshold)
            .order_by(desc(InboundEvent.processed_at))
            .limit(limit)
            .all()
        )

        # Privacy-safe utility functions
        def mask_phone_number(phone):
            """Mask phone number showing only last 4 digits"""
            if not phone or len(phone) < 4:
                return "****"
            return "*" * (len(phone) - 4) + phone[-4:]
        
        def classify_message(normalized_body):
            """Classify message content for privacy-safe monitoring"""
            if not normalized_body:
                return "Media Message"
            
            stop_keywords = ['stop', 'stopall', 'unsubscribe', 'cancel', 'end', 'quit', 'opt-out']
            if any(keyword in normalized_body.lower() for keyword in stop_keywords):
                return "STOP Command"
            
            if len(normalized_body.strip()) == 0:
                return "Empty Message"
            
            return "Text Reply"

        # Format response with privacy-safe data
        events = []
        for event in inbound_events:
            events.append(
                {
                    "event_id": event.id,
                    "masked_phone": mask_phone_number(event.from_phone),
                    "from_phone": event.from_phone,  # Keep for backend processing
                    "channel_type": event.channel_type,
                    "message_classification": classify_message(event.normalized_body),
                    "received_at": event.processed_at,
                    "processed": True,  # Assuming all stored events are processed
                    # Include normalized_body for backend processing but not display
                    "normalized_body": event.normalized_body,
                }
            )

        return (
            jsonify(
                {
                    "events": events,
                    "total_count": len(events),
                    "time_range_hours": hours,
                    "generated_at": datetime.utcnow(),
                }
            ),
            200,
        )

    except Exception as e:
        return (
            jsonify(
                ErrorResponse(
                    error="Internal Server Error",
                    message=f"Failed to get inbound events: {str(e)}",
                ).dict()
            ),
            500,
        )


@api_v1.route("/monitoring/dashboard", methods=["GET"])
def get_reporting_dashboard():
    """
    Get overall system health and metrics for monitoring dashboard
    Endpoint: GET /api/v1/monitoring/dashboard
    """
    try:
        # Calculate time thresholds
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)

        # System health metrics - optimized with fewer queries
        active_campaigns = Campaign.query.filter(
            Campaign.status.in_(["READY", "RUNNING"])
        ).count()

        # User metrics with single query
        user_stats = db.session.query(
            func.count(User.phone_e164).label("total_users"),
            func.sum(
                case((User.consent_state.in_(["OPT_OUT", "STOP"]), 1), else_=0)
            ).label("opted_out_users"),
        ).first()

        total_users = user_stats.total_users or 0
        opted_out_users = user_stats.opted_out_users or 0

        # Recent activity (24h) - optimized queries
        recent_inbound = InboundEvent.query.filter(
            InboundEvent.processed_at >= day_ago
        ).count()

        # Message metrics with single query
        message_stats = (
            db.session.query(
                func.sum(
                    case((Message.status.in_(["SENT", "DELIVERED"]), 1), else_=0)
                ).label("sent_24h")
            )
            .filter(Message.created_at >= day_ago)
            .first()
        )

        messages_sent_24h = message_stats.sent_24h or 0

        # Get delivered count via delivery receipts
        messages_delivered_24h = (
            db.session.query(func.count(DeliveryReceipt.id))
            .join(Message, Message.provider_sid == DeliveryReceipt.message_sid)
            .filter(
                Message.created_at >= day_ago,
                DeliveryReceipt.message_status == "delivered",
            )
            .scalar()
            or 0
        )

        # Calculate overall delivery rate
        total_sent = Message.query.filter(
            Message.status.in_(["SENT", "DELIVERED"])
        ).count()
        total_delivered = (
            db.session.query(func.count(DeliveryReceipt.id))
            .join(Message, Message.provider_sid == DeliveryReceipt.message_sid)
            .filter(DeliveryReceipt.message_status == "delivered")
            .scalar()
            or 0
        )

        overall_delivery_rate = (
            (total_delivered / total_sent * 100) if total_sent > 0 else 0.0
        )

        # Recent errors
        recent_errors_query = (
            Message.query.filter(
                Message.created_at >= day_ago, Message.error_code.isnot(None)
            )
            .order_by(desc(Message.created_at))
            .limit(10)
            .all()
        )

        recent_errors = [
            {
                "message_id": msg.id,
                "error_code": msg.error_code,
                "error_message": msg.error_message,
                "user_phone": msg.user_phone,
                "timestamp": msg.created_at,
            }
            for msg in recent_errors_query
        ]

        response_data = {
            "active_campaigns": active_campaigns,
            "recent_inbound_events": recent_inbound,
            "total_users": total_users,
            "opted_out_users": opted_out_users,
            "messages_sent_24h": messages_sent_24h,
            "messages_delivered_24h": messages_delivered_24h,
            "inbound_messages_24h": recent_inbound,
            "overall_delivery_rate": round(overall_delivery_rate, 2),
            "average_campaign_execution_time": None,  # Would need task analysis
            "recent_errors": recent_errors,
            "generated_at": now,
        }

        return jsonify(ReportingDashboardResponse(**response_data).dict()), 200

    except Exception as e:
        return (
            jsonify(
                ErrorResponse(
                    error="Internal Server Error",
                    message=f"Failed to get dashboard metrics: {str(e)}",
                ).dict()
            ),
            500,
        )
