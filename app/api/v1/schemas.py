"""
Marshmallow schemas for API serialization and validation
Ensures data integrity between API and SQLAlchemy models
"""
from marshmallow import Schema, fields, validate, validates, ValidationError, post_load
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from app.core.data_model import User, Campaign, Template, Segment, ConsentState, MessageStatus
import re

class UserSchema(SQLAlchemyAutoSchema):
    """User serialization schema with E.164 validation"""
    
    class Meta:
        model = User
        load_instance = True
        include_fk = True
    
    phone_e164 = fields.String(
        required=True,
        validate=validate.Length(max=16),
        metadata={'description': 'E.164 formatted phone number'}
    )
    
    attributes = fields.Dict(
        missing=dict,
        metadata={'description': 'Custom user attributes as JSON'}
    )
    
    consent_state = fields.Enum(
        ConsentState,
        by_value=True,
        missing=ConsentState.OPT_IN,
        metadata={'description': 'User consent state'}
    )
    
    @validates('phone_e164')
    def validate_phone_e164(self, value):
        """Validate E.164 format"""
        if not re.match(r'^\+[1-9]\d{1,14}$', value):
            raise ValidationError('Phone must be in valid E.164 format (+1234567890)')

class UserListSchema(Schema):
    """Schema for paginated user lists"""
    users = fields.List(fields.Nested(UserSchema))
    total = fields.Integer()
    page = fields.Integer()
    per_page = fields.Integer()
    has_next = fields.Boolean()
    has_prev = fields.Boolean()

class SegmentSchema(SQLAlchemyAutoSchema):
    """Segment definition schema"""
    
    class Meta:
        model = Segment
        load_instance = True
    
    name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100),
        metadata={'description': 'Segment name'}
    )
    
    definition_json = fields.Dict(
        required=True,
        metadata={'description': 'JSON filter definition for user segmentation'}
    )
    
    @validates('definition_json')
    def validate_definition_json(self, value):
        """Basic validation for segment definition structure"""
        if not isinstance(value, dict):
            raise ValidationError('Segment definition must be a JSON object')
        
        # Basic structure validation
        allowed_keys = {'attribute', 'operator', 'value', 'conditions', 'logic'}
        if not any(key in value for key in allowed_keys):
            raise ValidationError('Segment definition must contain valid filter criteria')

class TemplateSchema(SQLAlchemyAutoSchema):
    """Template schema for campaign content"""
    
    class Meta:
        model = Template
        load_instance = True
    
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    content = fields.String(required=True, validate=validate.Length(min=1))
    channel = fields.String(missing='whatsapp')
    locale = fields.String(missing='en_US')

class CampaignSchema(SQLAlchemyAutoSchema):
    """Campaign schema with nested relationships"""
    
    class Meta:
        model = Campaign
        load_instance = True
        include_fk = True
    
    topic = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100),
        metadata={'description': 'Campaign topic'}
    )
    
    template_id = fields.Integer(
        required=True,
        metadata={'description': 'ID of the template to use'}
    )
    
    status = fields.String(
        missing='DRAFT',
        validate=validate.OneOf(['DRAFT', 'READY', 'RUNNING', 'COMPLETED', 'PAUSED']),
        metadata={'description': 'Campaign status'}
    )
    
    rate_limit_per_second = fields.Integer(
        missing=10,
        validate=validate.Range(min=1, max=1000),
        metadata={'description': 'Message rate limit per second'}
    )
    
    quiet_hours_start = fields.String(
        validate=validate.Regexp(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'),
        allow_none=True,
        metadata={'description': 'Quiet hours start time (HH:MM format)'}
    )
    
    quiet_hours_end = fields.String(
        validate=validate.Regexp(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'),
        allow_none=True,
        metadata={'description': 'Quiet hours end time (HH:MM format)'}
    )
    
    # Nested template data for read operations
    template = fields.Nested(TemplateSchema, dump_only=True)

class CampaignListSchema(Schema):
    """Schema for paginated campaign lists"""
    campaigns = fields.List(fields.Nested(CampaignSchema))
    total = fields.Integer()
    page = fields.Integer()
    per_page = fields.Integer()

class CampaignTriggerSchema(Schema):
    """Schema for campaign trigger requests"""
    segment_id = fields.Integer(
        allow_none=True,
        metadata={'description': 'Optional segment ID to filter recipients'}
    )
    
    immediate = fields.Boolean(
        missing=False,
        metadata={'description': 'Whether to trigger immediately or respect schedule'}
    )
    
    dry_run = fields.Boolean(
        missing=False,
        metadata={'description': 'Whether to simulate without sending messages'}
    )

# Error response schemas
class ErrorSchema(Schema):
    """Standard error response schema"""
    error = fields.String(required=True)
    message = fields.String(required=True)
    code = fields.Integer()
    details = fields.Dict()

class ValidationErrorSchema(Schema):
    """Validation error response schema"""
    error = fields.String(default='Validation Error')
    message = fields.String(required=True)
    field_errors = fields.Dict()