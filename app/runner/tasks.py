"""
Celery tasks for bulk ingestion and trigger processing
Handles heavy lifting of data processing asynchronously
"""

import json
import csv
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.exc import IntegrityError
from app.main import db, create_app
from app.main import celery_app
from app.core.data_model import (
    User,
    Campaign,
    Segment,
    Template,
    Message,
    ConsentState,
    MessageStatus,
)
from app.core.rate_limiter import rate_limiter
from app.core.twilio_service import twilio_service
import logging

# Configure logging for campaign tasks
logger = logging.getLogger(__name__)


def get_flask_app():
    """Get Flask app context for database operations"""
    return create_app()


@celery_app.task(bind=True, max_retries=3)
def bulk_ingest_users(self, file_path: str, file_format: str = "csv") -> Dict[str, Any]:
    """
    Bulk ingest users from CSV/JSON file with E.164 validation and deduplication

    Args:
        file_path: Path to the uploaded file
        file_format: 'csv' or 'json'

    Returns:
        Dict with processing results and statistics
    """
    app = get_flask_app()

    with app.app_context():
        try:
            results = {
                "total_processed": 0,
                "successful": 0,
                "failed": 0,
                "duplicates_merged": 0,
                "errors": [],
                "started_at": datetime.utcnow().isoformat(),
                "file_path": file_path,
            }

            # Validate file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Process based on file format
            if file_format.lower() == "csv":
                records = _process_csv_file(file_path)
            elif file_format.lower() in ["json", "jsonl"]:
                records = _process_json_file(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_format}")

            # Process each record
            for record in records:
                results["total_processed"] += 1

                try:
                    # Validate and process user record
                    processed_user = _process_user_record(
                        record, results["total_processed"]
                    )

                    if processed_user:
                        # Perform upsert operation
                        user_result = _upsert_user(processed_user)

                        if user_result["action"] == "created":
                            results["successful"] += 1
                        elif user_result["action"] == "merged":
                            results["duplicates_merged"] += 1
                            results["successful"] += 1

                except Exception as record_error:
                    results["failed"] += 1
                    results["errors"].append(
                        {
                            "record_number": results["total_processed"],
                            "error": str(record_error),
                            "record_data": record,
                        }
                    )

                    # Continue processing other records
                    continue

            # Commit all changes
            db.session.commit()

            results["completed_at"] = datetime.utcnow().isoformat()

            # Clean up file
            try:
                os.remove(file_path)
            except OSError:
                pass  # File cleanup is not critical

            return results

        except Exception as e:
            db.session.rollback()
            # Retry logic for transient failures
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=60, exc=e)

            return {
                "total_processed": results.get("total_processed", 0),
                "successful": 0,
                "failed": results.get("total_processed", 0),
                "duplicates_merged": 0,
                "errors": [{"error": f"Task failed: {str(e)}"}],
                "completed_at": datetime.utcnow().isoformat(),
            }


@celery_app.task(bind=True, max_retries=3)
def process_trigger_event(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process real-time trigger events and queue campaign execution

    Args:
        event_payload: JSON event data with campaign/segment information

    Returns:
        Dict with processing results
    """
    app = get_flask_app()

    with app.app_context():
        try:
            results = {
                "event_id": event_payload.get("event_id"),
                "processed_at": datetime.utcnow().isoformat(),
                "status": "processing",
            }

            # Parse and validate event payload
            event_type = event_payload.get("type")
            campaign_id = event_payload.get("campaign_id")
            segment_id = event_payload.get("segment_id")

            if not event_type:
                raise ValueError("Event payload missing 'type' field")

            # Resolve campaign and segment
            campaign = None
            segment = None

            if campaign_id:
                campaign = Campaign.query.get(campaign_id)
                if not campaign:
                    raise ValueError(f"Campaign not found: {campaign_id}")

            if segment_id:
                segment = Segment.query.get(segment_id)
                if not segment:
                    raise ValueError(f"Segment not found: {segment_id}")

            # Queue campaign runner task (Phase 3.0 implementation)
            # For now, we'll just validate and log the trigger
            if campaign:
                results["campaign_topic"] = campaign.topic
                results["template_id"] = campaign.template_id

                # TODO: Queue actual campaign execution task
                # execute_campaign.delay(campaign.id, segment.id if segment else None, event_payload)

                results["status"] = "queued_for_execution"
            else:
                results["status"] = "validated_no_campaign"

            if segment:
                results["segment_name"] = segment.name
                results["segment_definition"] = segment.definition_json

            return results

        except Exception as e:
            # Retry logic for transient failures
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=30, exc=e)

            return {
                "event_id": event_payload.get("event_id"),
                "processed_at": datetime.utcnow().isoformat(),
                "status": "failed",
                "error": str(e),
            }


def _process_csv_file(file_path: str):
    """Process CSV file and yield records"""
    with open(file_path, "r", encoding="utf-8") as csvfile:
        # Detect delimiter
        sample = csvfile.read(1024)
        csvfile.seek(0)
        delimiter = "," if "," in sample else ";"

        reader = csv.DictReader(csvfile, delimiter=delimiter)
        for row in reader:
            yield row


def _process_json_file(file_path: str):
    """Process JSON/JSONL file and yield records"""
    with open(file_path, "r", encoding="utf-8") as jsonfile:
        content = jsonfile.read().strip()

        # Handle both JSON array and JSONL formats
        if content.startswith("["):
            # JSON array format
            data = json.loads(content)
            for record in data:
                yield record
        else:
            # JSONL format (one JSON object per line)
            for line in content.split("\n"):
                if line.strip():
                    yield json.loads(line)


def _process_user_record(record: Dict[str, Any], record_number: int) -> Dict[str, Any]:
    """
    Process and validate a single user record

    Args:
        record: Raw record from file
        record_number: Record position for error reporting

    Returns:
        Processed and validated user data
    """
    # Extract phone number with channel prefix removal
    phone_raw = record.get(
        "phone", record.get("phone_e164", record.get("phone_number"))
    )
    if not phone_raw:
        raise ValueError(f"Missing phone number in record {record_number}")

    # Remove channel prefixes (whatsapp:, sms:, etc.)
    phone_cleaned = re.sub(
        r"^(whatsapp:|sms:|messenger:|voice:)", "", str(phone_raw).strip()
    )

    # Validate E.164 format
    if not re.match(r"^\+[1-9]\d{1,14}$", phone_cleaned):
        raise ValueError(f"Invalid E.164 phone format: {phone_cleaned}")

    # Extract consent state
    consent_raw = record.get("consent_state", record.get("consent", "OPT_IN"))
    try:
        consent_state = ConsentState(consent_raw.upper())
    except ValueError:
        consent_state = ConsentState.OPT_IN  # Default to OPT_IN

    # Extract and clean attributes
    attributes = {}
    for key, value in record.items():
        if key not in [
            "phone",
            "phone_e164",
            "phone_number",
            "consent_state",
            "consent",
        ]:
            if value is not None and str(value).strip():
                attributes[key] = str(value).strip()

    return {
        "phone_e164": phone_cleaned,
        "consent_state": consent_state,
        "attributes": attributes,
    }


def _upsert_user(user_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Perform upsert operation for user with attribute merging

    Args:
        user_data: Processed user data

    Returns:
        Dict with action taken ('created' or 'merged')
    """
    phone_e164 = user_data["phone_e164"]

    # Check if user exists
    existing_user = User.query.get(phone_e164)

    if existing_user:
        # Merge attributes (new attributes override existing ones)
        merged_attributes = (
            existing_user.attributes.copy() if existing_user.attributes else {}
        )
        merged_attributes.update(user_data["attributes"])

        # Update existing user
        existing_user.attributes = merged_attributes
        existing_user.consent_state = user_data["consent_state"]
        existing_user.updated_at = datetime.utcnow()

        return {"action": "merged", "phone": phone_e164}
    else:
        # Create new user
        new_user = User(
            phone_e164=phone_e164,
            attributes=user_data["attributes"],
            consent_state=user_data["consent_state"],
        )

        db.session.add(new_user)
        return {"action": "created", "phone": phone_e164}


# ============================================================================
# CAMPAIGN ORCHESTRATION HELPER FUNCTIONS
# ============================================================================


def resolve_campaign_recipients(campaign: Campaign) -> List[User]:
    """
    Resolve all users that should receive messages for this campaign
    Based on segment definition and consent state

    Args:
        campaign: Campaign object with segment information

    Returns:
        List of User objects matching the segment criteria
    """
    # If no specific segment, get all opted-in users
    if not hasattr(campaign, "segment") or not campaign.segment:
        return User.query.filter(User.consent_state == ConsentState.OPT_IN).all()

    # Apply segment definition JSON filter
    segment = campaign.segment
    segment_definition = segment.definition_json

    # Start with base query
    query = User.query

    # Apply segment filters based on JSON definition
    if isinstance(segment_definition, dict):
        # Simple attribute-based filter
        if "attribute" in segment_definition:
            attribute_name = segment_definition["attribute"]
            operator = segment_definition.get("operator", "equals")
            value = segment_definition["value"]

            if attribute_name == "consent_state":
                # Direct field filter
                if operator == "equals":
                    consent_value = ConsentState(value)
                    query = query.filter(User.consent_state == consent_value)
            else:
                # JSON attribute filter
                if operator == "equals":
                    query = query.filter(
                        User.attributes[attribute_name].astext == str(value)
                    )
                elif operator == "contains":
                    query = query.filter(
                        User.attributes[attribute_name].astext.ilike(f"%{value}%")
                    )

        # Complex conditions with logic
        elif "conditions" in segment_definition:
            conditions = segment_definition["conditions"]
            logic = segment_definition.get("logic", "AND")

            filters = []
            for condition in conditions:
                attribute_name = condition["attribute"]
                operator = condition.get("operator", "equals")
                value = condition["value"]

                if operator == "equals":
                    filters.append(User.attributes[attribute_name].astext == str(value))
                elif operator == "contains":
                    filters.append(
                        User.attributes[attribute_name].astext.ilike(f"%{value}%")
                    )

            if logic == "AND":
                query = query.filter(db.and_(*filters))
            elif logic == "OR":
                query = query.filter(db.or_(*filters))

    return query.all()


def is_in_quiet_hours(campaign: Campaign, user: User) -> bool:
    """
    Check if current time is within campaign quiet hours for the user

    Args:
        campaign: Campaign with quiet hours configuration
        user: User object (could have timezone info in attributes)

    Returns:
        True if currently in quiet hours, False otherwise
    """
    if not campaign.quiet_hours_start or not campaign.quiet_hours_end:
        return False

    # Parse quiet hours (format: "HH:MM")
    try:
        start_time = datetime.strptime(campaign.quiet_hours_start, "%H:%M").time()
        end_time = datetime.strptime(campaign.quiet_hours_end, "%H:%M").time()
    except ValueError:
        logger.warning(f"Invalid quiet hours format for campaign {campaign.id}")
        return False

    # Get current time using local timezone (host timezone) instead of UTC
    # This respects the operator's local timezone by default
    current_time = datetime.now().time()

    # Handle overnight quiet hours (e.g., 22:00 to 06:00)
    if start_time > end_time:
        return current_time >= start_time or current_time <= end_time
    else:
        return start_time <= current_time <= end_time


def render_message_template(
    template_content: str, user_attributes: Dict[str, Any]
) -> str:
    """
    Render message template with user attributes

    Args:
        template_content: Template string with {placeholder} format
        user_attributes: User attributes dictionary

    Returns:
        Rendered message content

    Raises:
        ValueError: If required placeholders are missing
    """
    # Find all placeholders in template
    placeholders = re.findall(r"\{(\w+)\}", template_content)

    # Check if all required placeholders have values
    missing_placeholders = []
    for placeholder in placeholders:
        if placeholder not in user_attributes or not user_attributes[placeholder]:
            missing_placeholders.append(placeholder)

    if missing_placeholders:
        raise ValueError(f"Missing required template data: {missing_placeholders}")

    # Render template with user attributes
    try:
        rendered = template_content.format(**user_attributes)
        return rendered
    except KeyError as e:
        raise ValueError(f"Template rendering failed: missing attribute {str(e)}")
    except Exception as e:
        raise ValueError(f"Template rendering error: {str(e)}")


# ============================================================================
# CAMPAIGN ORCHESTRATION TASKS
# ============================================================================


@celery_app.task(bind=True, max_retries=3)
def check_scheduled_campaigns(self):
    """
    Celery Beat task to check for scheduled campaigns ready to run
    Runs every 30 seconds to check for READY campaigns
    """
    app = create_app()

    with app.app_context():
        try:
            # Find campaigns that are READY and either have no schedule_time or schedule_time <= now
            now = datetime.utcnow()

            ready_campaigns = Campaign.query.filter(
                Campaign.status == "READY",
                db.or_(Campaign.schedule_time.is_(None), Campaign.schedule_time <= now),
            ).all()

            results = []
            for campaign in ready_campaigns:
                # Queue the campaign for execution
                task = run_campaign_task.delay(campaign.id)

                # Update campaign status to RUNNING
                campaign.status = "RUNNING"
                db.session.commit()

                results.append(
                    {
                        "campaign_id": campaign.id,
                        "topic": campaign.topic,
                        "task_id": task.id,
                    }
                )

                logger.info(
                    f"Queued campaign {campaign.id} ({campaign.topic}) for execution"
                )

            return {
                "checked_at": now.isoformat(),
                "campaigns_queued": len(results),
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error checking scheduled campaigns: {str(e)}")
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=60, exc=e)
            return {"error": str(e), "checked_at": datetime.utcnow().isoformat()}


@celery_app.task(bind=True, max_retries=3)
def cleanup_old_rate_limits(self):
    """
    Cleanup old Redis rate limit keys to prevent memory buildup
    Runs every 5 minutes via Celery Beat
    """
    try:
        # This is handled automatically by Redis TTL, but we can add cleanup logic here
        # For now, just return success
        return {"cleaned_at": datetime.utcnow().isoformat(), "status": "completed"}
    except Exception as e:
        logger.error(f"Error cleaning up rate limits: {str(e)}")
        return {"error": str(e), "cleaned_at": datetime.utcnow().isoformat()}


@celery_app.task(bind=True, max_retries=3)
def run_campaign_task(self, campaign_id: int):
    """
    Main campaign orchestration task - processes all recipients with full compliance checks

    Args:
        campaign_id: ID of the campaign to execute

    Returns:
        Dict with comprehensive execution results and audit trail
    """
    app = create_app()

    with app.app_context():
        try:
            # Initialize results tracking
            results = {
                "campaign_id": campaign_id,
                "started_at": datetime.utcnow().isoformat(),
                "status": "processing",
                "recipients_processed": 0,
                "messages_sent": 0,
                "messages_failed": 0,
                "skipped_reasons": {
                    "opt_out": 0,
                    "quiet_hours": 0,
                    "rate_limit": 0,
                    "invalid_phone": 0,
                    "missing_template_data": 0,
                },
                "errors": [],
            }

            # 1. Load and validate campaign
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")

            if campaign.status != "RUNNING":
                raise ValueError(f"Campaign {campaign_id} is not in RUNNING status")

            # Load template
            template = Template.query.get(campaign.template_id)
            if not template:
                raise ValueError(f"Template {campaign.template_id} not found")

            # 2. Recipient Resolution - Query users based on segment definition
            recipients = resolve_campaign_recipients(campaign)
            results["total_recipients"] = len(recipients)

            logger.info(
                f"Campaign {campaign_id}: Processing {len(recipients)} recipients"
            )

            # 3. Process each recipient with full compliance pipeline
            for user in recipients:
                try:
                    results["recipients_processed"] += 1

                    # Compliance Check: Consent State
                    if user.consent_state != ConsentState.OPT_IN:
                        results["skipped_reasons"]["opt_out"] += 1
                        logger.debug(
                            f"Skipped user {user.phone_number}: consent state = {user.consent_state}"
                        )
                        continue

                    # Compliance Check: Quiet Hours
                    if is_in_quiet_hours(campaign, user):
                        results["skipped_reasons"]["quiet_hours"] += 1
                        logger.debug(f"Skipped user {user.phone_number}: quiet hours")
                        continue

                    # Rate Limit Check
                    rate_allowed, current_count, remaining = (
                        rate_limiter.check_and_increment(
                            campaign_id, campaign.rate_limit_per_second
                        )
                    )

                    if not rate_allowed:
                        results["skipped_reasons"]["rate_limit"] += 1
                        logger.warning(
                            f"Rate limit exceeded for campaign {campaign_id}: {current_count}/{campaign.rate_limit_per_second}"
                        )

                        # If rate limited, pause for 1 second and retry
                        if self.request.retries < self.max_retries:
                            raise self.retry(
                                countdown=1, exc=Exception("Rate limit exceeded")
                            )
                        continue

                    # Message Rendering
                    try:
                        rendered_content = render_message_template(
                            template.content, user.attributes
                        )
                    except Exception as e:
                        results["skipped_reasons"]["missing_template_data"] += 1
                        results["errors"].append(
                            {
                                "phone_number": user.phone_number,
                                "error": f"Template rendering failed: {str(e)}",
                            }
                        )
                        continue

                    # Message Materialization - Create Message record BEFORE API call
                    message = Message(
                        phone_number=user.phone_number,
                        campaign_id=campaign.id,
                        template_id=template.id,
                        rendered_content=rendered_content,
                        status=MessageStatus.QUEUED,
                        channel=template.channel,
                    )

                    db.session.add(message)
                    db.session.flush()  # Get the message ID without committing

                    # Twilio API Call
                    twilio_result = twilio_service.send_message(
                        to_phone=user.phone_number,
                        message_content=rendered_content,
                        channel=template.channel,
                    )

                    # Update message record with Twilio response
                    if twilio_result["success"]:
                        message.status = MessageStatus.SENT
                        message.provider_sid = twilio_result["message_sid"]
                        message.sent_at = datetime.utcnow()
                        results["messages_sent"] += 1

                        logger.info(
                            f"Message sent successfully: {user.phone_number} -> {twilio_result['message_sid']}"
                        )

                    else:
                        message.status = MessageStatus.FAILED
                        message.error_code = twilio_result["error_code"]
                        message.error_message = twilio_result["error_message"]
                        results["messages_failed"] += 1

                        results["errors"].append(
                            {
                                "phone_number": user.phone_number,
                                "error_code": twilio_result["error_code"],
                                "error_message": twilio_result["error_message"],
                            }
                        )

                        logger.error(
                            f"Message failed: {user.phone_number} -> {twilio_result['error_message']}"
                        )

                    # Commit the message record
                    db.session.commit()

                except Exception as recipient_error:
                    db.session.rollback()
                    results["errors"].append(
                        {"phone_number": user.phone_number, "error": str(recipient_error)}
                    )
                    logger.error(
                        f"Error processing recipient {user.phone_number}: {str(recipient_error)}"
                    )
                    continue

            # Update campaign status
            campaign.status = "COMPLETED"
            db.session.commit()

            results["status"] = "completed"
            results["completed_at"] = datetime.utcnow().isoformat()

            logger.info(
                f"Campaign {campaign_id} completed: {results['messages_sent']} sent, {results['messages_failed']} failed"
            )

            return results

        except Exception as e:
            db.session.rollback()

            # Update campaign status to indicate failure
            try:
                campaign = Campaign.query.get(campaign_id)
                if campaign:
                    campaign.status = "READY"  # Reset to allow retry
                    db.session.commit()
            except:
                pass

            logger.error(f"Campaign {campaign_id} execution failed: {str(e)}")

            # Retry logic
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=300, exc=e)  # Retry after 5 minutes

            results["status"] = "failed"
            results["error"] = str(e)
            results["failed_at"] = datetime.utcnow().isoformat()

            return results


@celery_app.task
def trigger_campaign_execution(campaign_id: int):
    """
    Manually trigger campaign execution (called from API endpoints)

    Args:
        campaign_id: ID of campaign to execute

    Returns:
        Task result from run_campaign_task
    """
    app = create_app()

    with app.app_context():
        # Validate campaign exists and is ready
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return {"error": f"Campaign {campaign_id} not found"}

        if campaign.status not in ["READY", "DRAFT"]:
            return {
                "error": f"Campaign {campaign_id} is not ready for execution (status: {campaign.status})"
            }

        # Update status and queue execution
        campaign.status = "RUNNING"
        db.session.commit()

        # Queue the actual execution task
        task = run_campaign_task.delay(campaign_id)

        return {
            "campaign_id": campaign_id,
            "task_id": task.id,
            "status": "queued",
            "message": "Campaign execution queued successfully",
        }
