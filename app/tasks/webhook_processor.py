"""
Webhook Processing Tasks - Asynchronous handlers for webhook normalization and complex processing
"""

from celery import Celery
from app.main import create_app, db, celery
from app.core.data_model import (
    InboundEvent,
    DeliveryReceipt,
    Message,
    User,
    ConsentState,
    MessageStatus,
)
import re
import json
from datetime import datetime


@celery.task
def process_inbound_message(event_id):
    """
    Asynchronous processing for inbound messages
    - Extract and normalize user data
    - Update user attributes based on message content
    - Link message to existing conversations
    """
    app = create_app()

    with app.app_context():
        try:
            # Fetch the raw event
            event = InboundEvent.query.get(event_id)
            if not event:
                print(f"Event {event_id} not found")
                return

            raw_payload = event.raw_payload

            # Extract normalized data
            from_phone = raw_payload.get("From")
            message_body = raw_payload.get("Body", "")
            profile_name = raw_payload.get("ProfileName", "")
            wa_id = raw_payload.get("WaId")  # WhatsApp ID

            # Extract channel and normalize phone number
            from app.core.data_model import extract_channel_and_phone

            channel_type, normalized_phone = extract_channel_and_phone(from_phone)

            # Update event with normalized data
            event.from_phone = normalized_phone
            event.normalized_body = message_body.lower().strip() if message_body else ""

            # Find or create user
            user = User.query.get(normalized_phone)
            if not user:
                user = User(
                    phone_number=normalized_phone,
                    consent_state=ConsentState.OPT_IN,
                    attributes={},
                )
                db.session.add(user)

            # Update user attributes with WhatsApp profile info
            if profile_name and profile_name != user.attributes.get("profile_name"):
                user.attributes = dict(user.attributes)  # Make mutable copy
                user.attributes["profile_name"] = profile_name
                user.updated_at = datetime.utcnow()

            if wa_id and wa_id != user.attributes.get("wa_id"):
                user.attributes = dict(user.attributes)
                user.attributes["wa_id"] = wa_id
                user.updated_at = datetime.utcnow()

            # Link event to user
            event.user_phone = normalized_phone

            # Process message commands and intents
            processed_intent = process_message_intent(message_body, user)
            if processed_intent:
                user.attributes = dict(user.attributes)
                user.attributes.update(processed_intent)
                user.updated_at = datetime.utcnow()

            db.session.commit()
            print(f"Processed inbound message from {normalized_phone}")

        except Exception as e:
            db.session.rollback()
            print(f"Error processing inbound message {event_id}: {e}")


@celery.task
def process_status_callback(receipt_id):
    """
    Asynchronous processing for delivery receipts
    - Update message status in messages table
    - Handle delivery confirmations and failures
    - Extract error details for failed messages
    """
    app = create_app()

    with app.app_context():
        try:
            # Fetch the raw receipt
            receipt = DeliveryReceipt.query.get(receipt_id)
            if not receipt:
                print(f"Receipt {receipt_id} not found")
                return

            raw_payload = receipt.raw_payload
            message_sid = raw_payload.get("MessageSid")
            message_status = raw_payload.get("MessageStatus")
            error_code = raw_payload.get("ErrorCode")

            # Find the corresponding message
            message = Message.query.filter_by(provider_sid=message_sid).first()
            if message:
                # Update message status
                old_status = message.status
                message.status = map_twilio_status_to_message_status(message_status)

                # Set timestamps based on status
                if (
                    message.status == MessageStatus.SENT
                    and old_status != MessageStatus.SENT
                ):
                    message.sent_at = datetime.utcnow()
                elif (
                    message.status == MessageStatus.DELIVERED
                    and old_status != MessageStatus.DELIVERED
                ):
                    message.delivered_at = datetime.utcnow()

                # Handle error codes
                if error_code:
                    message.error_code = int(error_code)

                # Link receipt to message and user
                receipt.message_id = message.id
                receipt.user_phone = message.recipient_phone

                print(
                    f"Updated message {message.id} status: {old_status} -> {message.status}"
                )
            else:
                print(f"Message not found for SID: {message_sid}")

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"Error processing status callback {receipt_id}: {e}")


def normalize_phone_number(phone):
    """
    Normalize phone number to E.164 format
    Handles various input formats from Twilio
    """
    if not phone:
        return phone

    # Remove whatsapp: prefix if present
    if phone.startswith("whatsapp:"):
        phone = phone[9:]

    # Already in E.164 format
    if phone.startswith("+") and re.match(r"^\+[1-9]\d{1,14}$", phone):
        return phone

    # Add + if missing but looks like E.164
    if re.match(r"^[1-9]\d{1,14}$", phone):
        return "+" + phone

    return phone  # Return as-is if can't normalize


def map_twilio_status_to_message_status(twilio_status):
    """
    Map Twilio message status to our internal MessageStatus enum
    """
    status_mapping = {
        "queued": MessageStatus.QUEUED,
        "sending": MessageStatus.SENDING,
        "sent": MessageStatus.SENT,
        "delivered": MessageStatus.DELIVERED,
        "read": MessageStatus.READ,
        "failed": MessageStatus.FAILED,
        "undelivered": MessageStatus.UNDELIVERED,
    }

    return status_mapping.get(twilio_status.lower(), MessageStatus.FAILED)


def process_message_intent(message_body, user):
    """
    Extract intent and context from user message
    Returns dictionary of attributes to update
    """
    if not message_body:
        return None

    body_lower = message_body.lower().strip()
    attributes = {}

    # Detect language preference
    if any(word in body_lower for word in ["සිංහල", "sinhala", "සින්හල"]):
        attributes["language"] = "si"
    elif any(word in body_lower for word in ["tamil", "தமிழ்"]):
        attributes["language"] = "ta"
    elif any(word in body_lower for word in ["english", "eng"]):
        attributes["language"] = "en"

    # Detect opt-in keywords
    if any(word in body_lower for word in ["start", "subscribe", "join", "yes"]):
        if user.consent_state == ConsentState.OPT_OUT:
            user.consent_state = ConsentState.OPT_IN

    # Store last message timestamp
    attributes["last_message_at"] = datetime.utcnow().isoformat()

    return attributes if attributes else None
