import uuid
import re
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Index,
    Enum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.schema import PrimaryKeyConstraint


# Get db from Flask app context
def get_db():
    from flask import current_app

    return current_app.extensions["sqlalchemy"]


class ConsentState(PyEnum):
    """The allowed states for a user's messaging consent."""

    OPT_IN = "OPT_IN"
    OPT_OUT = "OPT_OUT"
    STOP = "STOP"  # Explicit STOP command


class MessageStatus(PyEnum):
    """The state machine for outbound messages."""

    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    UNDELIVERED = "UNDELIVERED"


# Import db instance for phone processing
from app.main import db


def extract_channel_and_phone(phone_input):
    """
    Extract channel type and normalize phone number to E.164 format
    Returns tuple: (channel_type, normalized_phone)
    """
    if not phone_input:
        return None, None

    # Extract channel type and strip prefix
    channel_type = None
    phone = phone_input

    if phone.startswith("whatsapp:"):
        channel_type = "whatsapp"
        phone = phone[9:]
    elif phone.startswith("sms:"):
        channel_type = "sms"
        phone = phone[4:]
    elif phone.startswith("messenger:"):
        channel_type = "messenger"
        phone = phone[10:]
    elif phone.startswith("voice:"):
        channel_type = "voice"
        phone = phone[6:]
    else:
        # Default to sms if no prefix (Twilio's default)
        channel_type = "sms"

    # Clean whitespace
    phone = phone.strip()

    # Already in valid E.164 format
    if phone.startswith("+") and re.match(r"^\+[1-9]\d{1,14}$", phone):
        return channel_type, phone

    # Add + if missing but looks like valid E.164
    if re.match(r"^[1-9]\d{1,14}$", phone):
        return channel_type, "+" + phone

    # Invalid format - return None for data quality
    return channel_type, None


def normalize_phone_to_e164(phone_input):
    """
    Legacy function - use extract_channel_and_phone for new code
    """
    _, normalized_phone = extract_channel_and_phone(phone_input)
    return normalized_phone


class User(db.Model):
    """
    Users (E.164 phone as PK, attributes JSON, consent state)
    The central entity for messaging recipients.
    """

    __tablename__ = "users"

    # Primary Key (PK) - E.164 phone as PK
    phone_e164 = Column(
        String(16),
        primary_key=True,
        comment="User's phone number in E.164 format (PK).",
    )

    # Attributes JSON - For personalization and segmentation
    attributes = Column(
        JSONB, default={}, comment="JSON object for custom user attributes."
    )

    # Consent State - Crucial for compliance and STOP command enforcement
    consent_state = Column(
        Enum(ConsentState),
        default=ConsentState.OPT_IN,
        comment="Current messaging consent state (OPT_IN/OPT_OUT/STOP).",
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="user")
    inbound_events = relationship("InboundEvent", back_populates="user")
    delivery_receipts = relationship("DeliveryReceipt", back_populates="user")


class Subscription(db.Model):
    """
    Subscriptions (user -> topic)
    """

    __tablename__ = "subscriptions"

    # Composite Primary Key (user_id + topic)
    user_phone = Column(String(16), ForeignKey("users.phone_e164"), nullable=False)
    topic = Column(
        String(100),
        nullable=False,
        comment="Messaging topic the user is subscribed to.",
    )

    __table_args__ = (PrimaryKeyConstraint("user_phone", "topic"),)

    # Relationships
    user = relationship("User", back_populates="subscriptions")


class Message(db.Model):
    """
    Messages (materialized per recipient; state machine; provider SIDs; error codes)
    """

    __tablename__ = "messages"

    id = Column(
        Text,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Internal unique message ID (UUID).",
    )

    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    recipient_phone = Column(String(16), ForeignKey("users.phone_e164"), nullable=False)

    # State Machine Core
    status = Column(
        Enum(MessageStatus),
        default=MessageStatus.QUEUED,
        comment="Current message status (QUEUED, SENT, DELIVERED, FAILED, etc.).",
    )

    # Audit & Provider Fields
    provider_sid = Column(
        String(50),
        index=True,
        unique=True,
        comment="Twilio MessageSID for callback tracking.",
    )
    error_code = Column(
        Integer,
        nullable=True,
        comment="Twilio ErrorCode on FAILED or UNDELIVERED status.",
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, comment="Timestamp when Twilio API call was made.")
    delivered_at = Column(DateTime, comment="Timestamp when message was delivered.")

    campaign = relationship("Campaign")
    recipient = relationship("User")
    delivery_receipt = relationship("DeliveryReceipt", back_populates="message")
    inbound_events = relationship("InboundEvent", back_populates="message")


class Campaign(db.Model):
    """
    Campaigns (topic, template, schedule, status, rate limit, quiet hours)
    """

    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)
    topic = Column(
        String(100),
        nullable=False,
        comment="The topic this campaign targets (e.g., 'price_alert').",
    )

    # Foreign Key to the template content
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)
    template = relationship("Template")

    # Foreign Key to the target segment
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    segment = relationship("Segment")

    schedule_time = Column(DateTime, comment="Scheduled time for the campaign launch.")
    status = Column(
        String(50),
        default="DRAFT",
        comment="Campaign status (DRAFT, READY, RUNNING, COMPLETED).",
    )

    # Outbound Logic Rules
    rate_limit_per_second = Column(
        Integer, default=10, comment="Max messages to send per second."
    )
    quiet_hours_start = Column(
        String(5), comment="Time (e.g., '22:00') to pause sending."
    )
    quiet_hours_end = Column(
        String(5), comment="Time (e.g., '08:00') to resume sending."
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("Message", back_populates="campaign")


class Template(db.Model):
    """
    Templates (channel=whatsapp, locale, {placeholders})
    """

    __tablename__ = "templates"

    id = Column(Integer, primary_key=True)
    name = Column(
        String(100),
        unique=True,
        nullable=False,
        comment="Internal name for the template.",
    )
    channel = Column(
        String(20),
        default="whatsapp",
        comment="Messaging channel (always 'whatsapp' here).",
    )
    locale = Column(
        String(10), default="en_US", comment="Language/locale for the message."
    )
    content = Column(Text, nullable=False, comment="Message text with {placeholders}.")
    created_at = Column(DateTime, default=datetime.utcnow)


class Segment(db.Model):
    """
    Segments (definition JSON/DSL)
    """

    __tablename__ = "segments"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    # The actual filter logic for recipient resolution
    definition_json = Column(
        JSONB,
        comment="JSON/DSL defining user filtering rules (e.g., {'attribute': 'city', 'value': 'Colombo'}).",
    )
    created_at = Column(DateTime, default=datetime.utcnow)


class InboundEvent(db.Model):
    """
    Events_Inbound (raw + normalized) - Audit log for incoming user commands.
    """

    __tablename__ = "events_inbound"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_payload = Column(
        JSONB, nullable=False, comment="Full, original JSON payload from Twilio."
    )

    # Normalized fields (for easy querying)
    message_sid = Column(String(50), index=True, comment="Twilio MessageSid.")
    from_phone = Column(
        String(16), index=True, comment="E.164 number that sent the message (From)."
    )
    channel_type = Column(
        String(20),
        index=True,
        comment="Channel type extracted from Twilio prefix (whatsapp, sms, messenger).",
    )
    normalized_body = Column(Text, comment="Cleaned and lowercased message body.")
    processed_at = Column(DateTime, default=datetime.utcnow)

    # Relationship columns
    message_id = Column(
        Text,
        ForeignKey("messages.id"),
        nullable=True,
        comment="Link to message if this was a reply.",
    )
    user_phone = Column(
        String(16),
        ForeignKey("users.phone_e164"),
        nullable=True,
        comment="Link to user who sent the message.",
    )

    # Relationships
    user = relationship("User", back_populates="inbound_events")
    message = relationship("Message", back_populates="inbound_events")


class DeliveryReceipt(db.Model):
    """
    Delivery_Receipts (raw + normalized) - Audit log for Twilio status callbacks.
    """

    __tablename__ = "delivery_receipts"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_payload = Column(
        JSONB,
        nullable=False,
        comment="Full, original JSON payload from Twilio status callback.",
    )

    # Normalized fields (for easy querying)
    message_sid = Column(
        String(50),
        index=True,
        comment="Twilio MessageSid of the message being updated.",
    )
    message_status = Column(
        String(20), index=True, comment="Final status (e.g., delivered, failed)."
    )
    error_code = Column(Integer, comment="Error code if delivery failed.")
    received_at = Column(DateTime, default=datetime.utcnow)

    # Foreign Keys for proper relationships
    message_id = Column(
        Text,
        ForeignKey("messages.id"),
        nullable=True,
        comment="Link to the message record if available.",
    )
    user_phone = Column(
        String(16),
        ForeignKey("users.phone_e164"),
        nullable=True,
        comment="Link to user for aggregated reporting.",
    )

    # Relationships
    message = relationship("Message", back_populates="delivery_receipt")
    user = relationship("User", back_populates="delivery_receipts")


# Performance Indexes for High-Traffic Queries
Index("idx_messages_status_created", Message.status, Message.created_at)
Index("idx_messages_recipient_phone", Message.recipient_phone)
Index("idx_delivery_receipts_message_sid", DeliveryReceipt.message_sid)
Index("idx_inbound_events_from_phone", InboundEvent.from_phone)
Index("idx_inbound_events_channel_type", InboundEvent.channel_type)
Index("idx_users_consent_state", User.consent_state)
