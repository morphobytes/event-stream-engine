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
    from_attributes=True,
    str_strip_whitespace=True,
    use_enum_values=True
)

# User schemas
class UserBase(BaseModel):
    phone_e164: str = Field(..., max_length=16, description="E.164 formatted phone number")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Custom user attributes")
    consent_state: ConsentStateEnum = Field(default=ConsentStateEnum.OPT_IN, description="User consent state")
    
    @validator('phone_e164')
    def validate_phone_e164(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone must be in valid E.164 format (+1234567890)')
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
    content: str = Field(..., min_length=1, description="Message content with {placeholders}")
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
    
    @validator('definition_json')
    def validate_definition_json(cls, v):
        if not isinstance(v, dict):
            raise ValueError('Segment definition must be a JSON object')
        
        allowed_keys = {'attribute', 'operator', 'value', 'conditions', 'logic'}
        if not any(key in v for key in allowed_keys):
            raise ValueError('Segment definition must contain valid filter criteria')
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
    status: CampaignStatusEnum = Field(default=CampaignStatusEnum.DRAFT, description="Campaign status")
    rate_limit_per_second: int = Field(default=10, ge=1, le=1000, description="Message rate limit per second")
    quiet_hours_start: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', description="Quiet hours start (HH:MM)")
    quiet_hours_end: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', description="Quiet hours end (HH:MM)")
    schedule_time: Optional[datetime] = Field(None, description="Scheduled launch time")

class CampaignCreate(CampaignBase):
    pass

class CampaignUpdate(BaseModel):
    status: Optional[CampaignStatusEnum] = None
    rate_limit_per_second: Optional[int] = Field(None, ge=1, le=1000)
    quiet_hours_start: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    quiet_hours_end: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
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
    segment_id: Optional[int] = Field(None, description="Optional segment ID to filter recipients")
    immediate: bool = Field(default=False, description="Whether to trigger immediately")
    dry_run: bool = Field(default=False, description="Whether to simulate without sending")

class CampaignTriggerResponse(BaseModel):
    message: str
    campaign_id: int
    status: CampaignStatusEnum
    dry_run: bool
    immediate: bool
    segment_id: Optional[int] = None

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