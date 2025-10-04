"""
Public API v1 - REST endpoints for Event Stream Engine
Implements CRUD operations for Users, Campaigns, Segments, and Triggers
"""
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import or_, and_
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError
from app.main import db
from app.core.data_model import User, Campaign, Template, Segment, ConsentState
from app.api.v1.schemas import (
    UserSchema, UserListSchema, CampaignSchema, CampaignListSchema,
    SegmentSchema, TemplateSchema, CampaignTriggerSchema, ErrorSchema, ValidationErrorSchema
)
from datetime import datetime
import math

# Create API Blueprint
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# Initialize schemas
user_schema = UserSchema()
users_schema = UserSchema(many=True)
user_list_schema = UserListSchema()
campaign_schema = CampaignSchema()
campaigns_schema = CampaignSchema(many=True)
campaign_list_schema = CampaignListSchema()
segment_schema = SegmentSchema()
segments_schema = SegmentSchema(many=True)
template_schema = TemplateSchema()
campaign_trigger_schema = CampaignTriggerSchema()

# Error handlers
def handle_validation_error(error):
    """Handle marshmallow validation errors"""
    return jsonify({
        'error': 'Validation Error',
        'message': 'Invalid input data',
        'field_errors': error.messages
    }), 400

def handle_integrity_error(error):
    """Handle database integrity errors"""
    return jsonify({
        'error': 'Database Error',
        'message': 'Data integrity constraint violated',
        'details': str(error.orig) if hasattr(error, 'orig') else str(error)
    }), 409

def handle_not_found(resource_type, identifier):
    """Handle resource not found errors"""
    return jsonify({
        'error': 'Not Found',
        'message': f'{resource_type} with identifier {identifier} not found'
    }), 404

# USERS ENDPOINTS
@api_v1.route('/users', methods=['GET'])
def get_users():
    """
    Get paginated list of users with filtering
    Query params: page, per_page, consent_state, topic
    """
    try:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)  # Max 100 per page
        
        # Build query with filters
        query = User.query
        
        # Filter by consent state
        consent_state = request.args.get('consent_state')
        if consent_state:
            try:
                consent_enum = ConsentState(consent_state.upper())
                query = query.filter(User.consent_state == consent_enum)
            except ValueError:
                return handle_validation_error(ValidationError({'consent_state': 'Invalid consent state'}))
        
        # Filter by subscription topic
        topic = request.args.get('topic')
        if topic:
            query = query.join(User.subscriptions).filter_by(topic=topic)
        
        # Execute paginated query
        paginated = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # Serialize results
        result = {
            'users': users_schema.dump(paginated.items),
            'total': paginated.total,
            'page': page,
            'per_page': per_page,
            'has_next': paginated.has_next,
            'has_prev': paginated.has_prev,
            'pages': paginated.pages
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

@api_v1.route('/users', methods=['POST'])
def create_user():
    """Create a new user with E.164 validation"""
    try:
        # Validate and deserialize input
        user_data = user_schema.load(request.json)
        
        # Check if user already exists
        existing_user = User.query.get(user_data.phone_e164)
        if existing_user:
            return jsonify({
                'error': 'Conflict',
                'message': f'User with phone {user_data.phone_e164} already exists'
            }), 409
        
        # Create new user
        new_user = User(
            phone_e164=user_data.phone_e164,
            attributes=user_data.attributes or {},
            consent_state=user_data.consent_state or ConsentState.OPT_IN
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify(user_schema.dump(new_user)), 201
        
    except ValidationError as e:
        return handle_validation_error(e)
    except IntegrityError as e:
        db.session.rollback()
        return handle_integrity_error(e)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

@api_v1.route('/users/<phone_e164>', methods=['PUT'])
def update_user(phone_e164):
    """Update user attributes or consent state"""
    try:
        # Find user
        user = User.query.get(phone_e164)
        if not user:
            return handle_not_found('User', phone_e164)
        
        # Validate input (partial update allowed)
        update_data = user_schema.load(request.json, partial=True)
        
        # Update fields
        if hasattr(update_data, 'attributes') and update_data.attributes is not None:
            user.attributes = update_data.attributes
        
        if hasattr(update_data, 'consent_state') and update_data.consent_state is not None:
            user.consent_state = update_data.consent_state
        
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify(user_schema.dump(user)), 200
        
    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

# SEGMENTS ENDPOINTS
@api_v1.route('/segments', methods=['GET'])
def get_segments():
    """Get all segment definitions"""
    try:
        segments = Segment.query.all()
        return jsonify({'segments': segments_schema.dump(segments)}), 200
    except Exception as e:
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

@api_v1.route('/segments', methods=['POST'])
def create_segment():
    """Create a new segment definition"""
    try:
        # Validate and deserialize input
        segment_data = segment_schema.load(request.json)
        
        # Check for duplicate name
        existing = Segment.query.filter_by(name=segment_data.name).first()
        if existing:
            return jsonify({
                'error': 'Conflict',
                'message': f'Segment with name {segment_data.name} already exists'
            }), 409
        
        # Create new segment
        new_segment = Segment(
            name=segment_data.name,
            definition_json=segment_data.definition_json
        )
        
        db.session.add(new_segment)
        db.session.commit()
        
        return jsonify(segment_schema.dump(new_segment)), 201
        
    except ValidationError as e:
        return handle_validation_error(e)
    except IntegrityError as e:
        db.session.rollback()
        return handle_integrity_error(e)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

# CAMPAIGNS ENDPOINTS
@api_v1.route('/campaigns', methods=['GET'])
def get_campaigns():
    """Get campaigns with status filtering"""
    try:
        # Build query with status filter
        query = Campaign.query
        
        status_filter = request.args.get('status')
        if status_filter:
            query = query.filter(Campaign.status == status_filter.upper())
        
        campaigns = query.all()
        
        return jsonify({
            'campaigns': campaigns_schema.dump(campaigns),
            'total': len(campaigns)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

@api_v1.route('/campaigns', methods=['POST'])
def create_campaign():
    """Create a new campaign"""
    try:
        # Validate and deserialize input
        campaign_data = campaign_schema.load(request.json)
        
        # Verify template exists
        template = Template.query.get(campaign_data.template_id)
        if not template:
            return handle_not_found('Template', campaign_data.template_id)
        
        # Create new campaign
        new_campaign = Campaign(
            topic=campaign_data.topic,
            template_id=campaign_data.template_id,
            status=campaign_data.status or 'DRAFT',
            rate_limit_per_second=campaign_data.rate_limit_per_second or 10,
            quiet_hours_start=campaign_data.quiet_hours_start,
            quiet_hours_end=campaign_data.quiet_hours_end,
            schedule_time=getattr(campaign_data, 'schedule_time', None)
        )
        
        db.session.add(new_campaign)
        db.session.commit()
        
        return jsonify(campaign_schema.dump(new_campaign)), 201
        
    except ValidationError as e:
        return handle_validation_error(e)
    except IntegrityError as e:
        db.session.rollback()
        return handle_integrity_error(e)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

@api_v1.route('/campaigns/<int:campaign_id>', methods=['PUT'])
def update_campaign(campaign_id):
    """Update campaign rules, schedule, or status"""
    try:
        # Find campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return handle_not_found('Campaign', campaign_id)
        
        # Validate input (partial update allowed)
        update_data = campaign_schema.load(request.json, partial=True)
        
        # Update fields
        for field in ['status', 'rate_limit_per_second', 'quiet_hours_start', 'quiet_hours_end', 'schedule_time']:
            if hasattr(update_data, field):
                value = getattr(update_data, field)
                if value is not None:
                    setattr(campaign, field, value)
        
        campaign.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify(campaign_schema.dump(campaign)), 200
        
    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

# CAMPAIGN TRIGGER ENDPOINT
@api_v1.route('/campaigns/<int:campaign_id>/trigger', methods=['POST'])
def trigger_campaign(campaign_id):
    """Trigger campaign execution (placeholder for Celery task)"""
    try:
        # Find campaign
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return handle_not_found('Campaign', campaign_id)
        
        # Validate trigger parameters
        trigger_data = campaign_trigger_schema.load(request.json or {})
        
        # Basic validation
        if campaign.status not in ['READY', 'DRAFT']:
            return jsonify({
                'error': 'Invalid State',
                'message': f'Campaign must be in READY or DRAFT state to trigger (current: {campaign.status})'
            }), 400
        
        # Verify template exists and is valid
        if not campaign.template:
            return jsonify({
                'error': 'Invalid Configuration',
                'message': 'Campaign template not found'
            }), 400
        
        # Update campaign status
        campaign.status = 'RUNNING' if not trigger_data.get('dry_run') else campaign.status
        campaign.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # TODO: Queue Celery task for campaign execution
        # from app.tasks.campaign_runner import execute_campaign
        # execute_campaign.delay(campaign_id, trigger_data)
        
        return jsonify({
            'message': 'Campaign trigger initiated',
            'campaign_id': campaign_id,
            'status': campaign.status,
            'dry_run': trigger_data.get('dry_run', False),
            'immediate': trigger_data.get('immediate', False),
            'segment_id': trigger_data.get('segment_id')
        }), 200
        
    except ValidationError as e:
        return handle_validation_error(e)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

# HEALTH CHECK
@api_v1.route('/health', methods=['GET'])
def api_health():
    """API health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': 'v1',
        'timestamp': datetime.utcnow().isoformat()
    }), 200