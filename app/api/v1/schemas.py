"""
Pydantic schemas for API serialization and validation
Modern Python type hints with automatic validation and superior performance
"""

from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import re


# Enums for validation
class ConsentStateEnum(str, Enum):
    OPT_IN = "OPT_IN"
    OPT_OUT = "OPT_OUT"
    STOP = "STOP"


class MessageStatusEnum(str, Enum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    UNDELIVERED = "UNDELIVERED"


class CampaignStatusEnum(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"


class ChannelTypeEnum(str, Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    MESSENGER = "messenger"
    VOICE = "voice"


# Pydantic v2 configuration
base_config = ConfigDict(
    from_attributes=True, str_strip_whitespace=True, use_enum_values=True
)


# User schemas
class UserBase(BaseModel):
    phone_e164: str = Field(
        ..., max_length=16, description="E.164 formatted phone number"
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Custom user attributes"
    )
    consent_state: ConsentStateEnum = Field(
        default=ConsentStateEnum.OPT_IN, description="User consent state"
    )

    @validator("phone_e164")
    def validate_phone_e164(cls, v):
        if not re.match(r"^\+[1-9]\d{1,14}$", v):
            raise ValueError("Phone must be in valid E.164 format (+1234567890)")
        return v


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    attributes: Optional[Dict[str, Any]] = None
    consent_state: Optional[ConsentStateEnum] = None


class UserResponse(UserBase):
    created_at: datetime
    updated_at: datetime

    model_config = base_config


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool
    pages: int


# Template schemas
class TemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    content: str = Field(
        ..., min_length=1, description="Message content with {placeholders}"
    )
    channel: str = Field(default="whatsapp", description="Channel type")
    locale: str = Field(default="en_US", description="Language/locale")


class TemplateCreate(TemplateBase):
    pass


class TemplateResponse(TemplateBase):
    id: int
    created_at: datetime

    model_config = base_config


# Segment schemas
class SegmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Segment name")
    definition_json: Dict[str, Any] = Field(..., description="JSON filter definition")

    @validator("definition_json")
    def validate_definition_json(cls, v):
        if not isinstance(v, dict):
            raise ValueError("Segment definition must be a JSON object")

        allowed_keys = {"attribute", "operator", "value", "conditions", "logic"}
        if not any(key in v for key in allowed_keys):
            raise ValueError("Segment definition must contain valid filter criteria")
        return v


class SegmentCreate(SegmentBase):
    pass


class SegmentResponse(SegmentBase):
    id: int
    created_at: datetime

    model_config = base_config


# Campaign schemas
class CampaignBase(BaseModel):
    topic: str = Field(..., min_length=1, max_length=100, description="Campaign topic")
    template_id: int = Field(..., description="ID of the template to use")
    status: CampaignStatusEnum = Field(
        default=CampaignStatusEnum.DRAFT, description="Campaign status"
    )
    rate_limit_per_second: int = Field(
        default=10, ge=1, le=1000, description="Message rate limit per second"
    )
    quiet_hours_start: Optional[str] = Field(
        None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours start (HH:MM)",
    )
    quiet_hours_end: Optional[str] = Field(
        None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours end (HH:MM)",
    )
    schedule_time: Optional[datetime] = Field(None, description="Scheduled launch time")


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    status: Optional[CampaignStatusEnum] = None
    rate_limit_per_second: Optional[int] = Field(None, ge=1, le=1000)
    quiet_hours_start: Optional[str] = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    quiet_hours_end: Optional[str] = Field(
        None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    schedule_time: Optional[datetime] = None


class CampaignResponse(CampaignBase):
    id: int
    created_at: datetime
    updated_at: datetime
    template: Optional[TemplateResponse] = None

    model_config = base_config


class CampaignListResponse(BaseModel):
    campaigns: List[CampaignResponse]
    total: int


# Campaign trigger schema
class CampaignTriggerRequest(BaseModel):
    segment_id: Optional[int] = Field(
        None, description="Optional segment ID to filter recipients"
    )
    immediate: bool = Field(default=False, description="Whether to trigger immediately")
    dry_run: bool = Field(
        default=False, description="Whether to simulate without sending"
    )


class CampaignTriggerResponse(BaseModel):
    message: str
    campaign_id: int
    status: CampaignStatusEnum
    dry_run: bool
    immediate: bool
    segment_id: Optional[int] = None
    task_id: Optional[str] = None


# Error response schemas
class ErrorResponse(BaseModel):
    error: str
    message: str
    code: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class ValidationErrorResponse(BaseModel):
    error: str = "Validation Error"
    message: str
    field_errors: Dict[str, List[str]]


# Health check schema
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


# Ingestion schemas
class BulkIngestionResponse(BaseModel):
    message: str
    task_id: str
    file_name: str
    estimated_processing_time: str


class TriggerEventRequest(BaseModel):
    event_id: Optional[str] = None
    type: str = Field(..., description="Event type (e.g., 'price_alert', 'welcome')")
    campaign_id: Optional[int] = Field(None, description="Campaign to execute")
    segment_id: Optional[int] = Field(None, description="Target segment filter")
    user_phone: Optional[str] = Field(None, description="Specific user phone (E.164)")
    event_data: Dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )


class TriggerEventResponse(BaseModel):
    message: str
    tasks: List[Dict[str, str]]
    processing_status: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    timestamp: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BulkIngestionResult(BaseModel):
    total_processed: int
    successful: int
    failed: int
    duplicates_merged: int
    started_at: str
    completed_at: Optional[str] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# REPORTING & MONITORING SCHEMAS (Phase 4.0)
# ============================================================================


class MessageStatusResponse(BaseModel):
    """Individual message status and tracking information"""

    model_config = base_config

    message_id: int
    user_phone: str
    campaign_id: int
    template_id: int
    rendered_content: str
    status: MessageStatusEnum
    channel: ChannelTypeEnum
    provider_sid: Optional[str] = None
    sent_at: Optional[datetime] = None
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime

    # Delivery receipt info (if available)
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None


class CampaignSummaryStats(BaseModel):
    """Campaign execution summary with business intelligence metrics"""

    model_config = base_config

    campaign_id: int
    campaign_topic: str
    campaign_status: str

    # Execution metrics
    total_recipients: int
    messages_queued: int
    messages_sent: int
    messages_delivered: int
    messages_failed: int

    # Compliance metrics
    opt_outs_during_campaign: int
    quiet_hours_skipped: int
    rate_limit_skipped: int
    template_errors: int

    # Performance metrics
    delivery_rate_percent: float
    success_rate_percent: float
    average_delivery_time_seconds: Optional[float] = None

    # Error analysis
    top_error_codes: List[Dict[str, Union[str, int]]] = Field(default_factory=list)

    # Timestamps
    campaign_started_at: Optional[datetime] = None
    campaign_completed_at: Optional[datetime] = None
    last_updated: datetime


class InboundEventResponse(BaseModel):
    """Inbound webhook event information for monitoring"""

    model_config = base_config

    event_id: int
    user_phone: str
    message_body: Optional[str] = None
    media_url: Optional[str] = None
    channel_type: str
    provider_sid: str
    received_at: datetime
    processed: bool

    # Normalized fields
    normalized_body: Optional[str] = None


class ReportingDashboardResponse(BaseModel):
    """Overall system health and metrics for dashboard"""

    model_config = base_config

    # System health
    active_campaigns: int
    recent_inbound_events: int
    total_users: int
    opted_out_users: int

    # Recent activity (last 24 hours)
    messages_sent_24h: int
    messages_delivered_24h: int
    inbound_messages_24h: int

    # Performance metrics
    overall_delivery_rate: float
    average_campaign_execution_time: Optional[float] = None

    # Error tracking
    recent_errors: List[Dict[str, Any]] = Field(default_factory=list)

    # Timestamp
    generated_at: datetime
