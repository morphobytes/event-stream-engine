"""
Campaign Orchestrator - Core Business Logic for Outbound Message Delivery
Handles the complete campaign execution pipeline with compliance and auditing
"""
import re
from datetime import datetime, time, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.exc import IntegrityError
from app.main import db, create_app

# Import the celery app instance
def get_celery_app():
    """Get the celery app instance"""
    from app.main import celery_app
    return celery_app
from app.core.data_model import (
    User, Campaign, Template, Segment, Message, 
    ConsentState, MessageStatus, CampaignStatus
)
from app.core.rate_limiter import rate_limiter
from app.core.twilio_service import twilio_service
import logging
import json

# Configure logging
logger = logging.getLogger(__name__)


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
                Campaign.status == CampaignStatus.READY,
                db.or_(
                    Campaign.schedule_time.is_(None),
                    Campaign.schedule_time <= now
                )
            ).all()
            
            results = []
            for campaign in ready_campaigns:
                # Queue the campaign for execution
                task = run_campaign_task.delay(campaign.id)
                
                # Update campaign status to RUNNING
                campaign.status = CampaignStatus.RUNNING
                db.session.commit()
                
                results.append({
                    'campaign_id': campaign.id,
                    'topic': campaign.topic,
                    'task_id': task.id
                })
                
                logger.info(f"Queued campaign {campaign.id} ({campaign.topic}) for execution")
            
            return {
                'checked_at': now.isoformat(),
                'campaigns_queued': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error checking scheduled campaigns: {str(e)}")
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=60, exc=e)
            return {'error': str(e), 'checked_at': datetime.utcnow().isoformat()}


@celery_app.task(bind=True, max_retries=3)
def cleanup_old_rate_limits(self):
    """
    Cleanup old Redis rate limit keys to prevent memory buildup
    Runs every 5 minutes via Celery Beat
    """
    try:
        # This is handled automatically by Redis TTL, but we can add cleanup logic here
        # For now, just return success
        return {
            'cleaned_at': datetime.utcnow().isoformat(),
            'status': 'completed'
        }
    except Exception as e:
        logger.error(f"Error cleaning up rate limits: {str(e)}")
        return {'error': str(e), 'cleaned_at': datetime.utcnow().isoformat()}


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
                'campaign_id': campaign_id,
                'started_at': datetime.utcnow().isoformat(),
                'status': 'processing',
                'recipients_processed': 0,
                'messages_sent': 0,
                'messages_failed': 0,
                'skipped_reasons': {
                    'opt_out': 0,
                    'quiet_hours': 0,
                    'rate_limit': 0,
                    'invalid_phone': 0,
                    'missing_template_data': 0
                },
                'errors': []
            }
            
            # 1. Load and validate campaign
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")
            
            if campaign.status != CampaignStatus.RUNNING:
                raise ValueError(f"Campaign {campaign_id} is not in RUNNING status")
            
            # Load template
            template = Template.query.get(campaign.template_id)
            if not template:
                raise ValueError(f"Template {campaign.template_id} not found")
            
            # 2. Recipient Resolution - Query users based on segment definition
            recipients = resolve_campaign_recipients(campaign)
            results['total_recipients'] = len(recipients)
            
            logger.info(f"Campaign {campaign_id}: Processing {len(recipients)} recipients")
            
            # 3. Process each recipient with full compliance pipeline
            for user in recipients:
                try:
                    results['recipients_processed'] += 1
                    
                    # Compliance Check: Consent State
                    if user.consent_state != ConsentState.OPT_IN:
                        results['skipped_reasons']['opt_out'] += 1
                        logger.debug(f"Skipped user {user.phone_e164}: consent state = {user.consent_state}")
                        continue
                    
                    # Compliance Check: Quiet Hours
                    if is_in_quiet_hours(campaign, user):
                        results['skipped_reasons']['quiet_hours'] += 1
                        logger.debug(f"Skipped user {user.phone_e164}: quiet hours")
                        continue
                    
                    # Rate Limit Check
                    rate_allowed, current_count, remaining = rate_limiter.check_and_increment(
                        campaign_id, campaign.rate_limit_per_second
                    )
                    
                    if not rate_allowed:
                        results['skipped_reasons']['rate_limit'] += 1
                        logger.warning(f"Rate limit exceeded for campaign {campaign_id}: {current_count}/{campaign.rate_limit_per_second}")
                        
                        # If rate limited, pause for 1 second and retry
                        if self.request.retries < self.max_retries:
                            raise self.retry(countdown=1, exc=Exception("Rate limit exceeded"))
                        continue
                    
                    # Message Rendering
                    try:
                        rendered_content = render_message_template(template.content, user.attributes)
                    except Exception as e:
                        results['skipped_reasons']['missing_template_data'] += 1
                        results['errors'].append({
                            'user_phone': user.phone_e164,
                            'error': f'Template rendering failed: {str(e)}'
                        })
                        continue
                    
                    # Message Materialization - Create Message record BEFORE API call
                    message = Message(
                        user_phone=user.phone_e164,
                        campaign_id=campaign.id,
                        template_id=template.id,
                        rendered_content=rendered_content,
                        status=MessageStatus.QUEUED,
                        channel=template.channel
                    )
                    
                    db.session.add(message)
                    db.session.flush()  # Get the message ID without committing
                    
                    # Twilio API Call
                    twilio_result = twilio_service.send_message(
                        to_phone=user.phone_e164,
                        message_content=rendered_content,
                        channel=template.channel
                    )
                    
                    # Update message record with Twilio response
                    if twilio_result['success']:
                        message.status = MessageStatus.SENT
                        message.provider_sid = twilio_result['message_sid']
                        message.sent_at = datetime.utcnow()
                        results['messages_sent'] += 1
                        
                        logger.info(f"Message sent successfully: {user.phone_e164} -> {twilio_result['message_sid']}")
                        
                    else:
                        message.status = MessageStatus.FAILED
                        message.error_code = twilio_result['error_code']
                        message.error_message = twilio_result['error_message']
                        results['messages_failed'] += 1
                        
                        results['errors'].append({
                            'user_phone': user.phone_e164,
                            'error_code': twilio_result['error_code'],
                            'error_message': twilio_result['error_message']
                        })
                        
                        logger.error(f"Message failed: {user.phone_e164} -> {twilio_result['error_message']}")
                    
                    # Commit the message record
                    db.session.commit()
                    
                except Exception as recipient_error:
                    db.session.rollback()
                    results['errors'].append({
                        'user_phone': user.phone_e164,
                        'error': str(recipient_error)
                    })
                    logger.error(f"Error processing recipient {user.phone_e164}: {str(recipient_error)}")
                    continue
            
            # Update campaign status
            campaign.status = CampaignStatus.COMPLETED
            db.session.commit()
            
            results['status'] = 'completed'
            results['completed_at'] = datetime.utcnow().isoformat()
            
            logger.info(f"Campaign {campaign_id} completed: {results['messages_sent']} sent, {results['messages_failed']} failed")
            
            return results
            
        except Exception as e:
            db.session.rollback()
            
            # Update campaign status to indicate failure
            try:
                campaign = Campaign.query.get(campaign_id)
                if campaign:
                    campaign.status = CampaignStatus.READY  # Reset to allow retry
                    db.session.commit()
            except:
                pass
            
            logger.error(f"Campaign {campaign_id} execution failed: {str(e)}")
            
            # Retry logic
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=300, exc=e)  # Retry after 5 minutes
            
            results['status'] = 'failed'
            results['error'] = str(e)
            results['failed_at'] = datetime.utcnow().isoformat()
            
            return results


def resolve_campaign_recipients(campaign: Campaign) -> List[User]:
    """
    Resolve campaign recipients based on segment definition
    
    Args:
        campaign: Campaign object with segment information
        
    Returns:
        List of User objects matching the segment criteria
    """
    # If no specific segment, get all opted-in users
    if not hasattr(campaign, 'segment') or not campaign.segment:
        return User.query.filter(User.consent_state == ConsentState.OPT_IN).all()
    
    # Apply segment definition JSON filter
    segment = campaign.segment
    segment_definition = segment.definition_json
    
    # Start with base query
    query = User.query
    
    # Apply segment filters based on JSON definition
    if isinstance(segment_definition, dict):
        # Simple attribute-based filter
        if 'attribute' in segment_definition:
            attribute_name = segment_definition['attribute']
            operator = segment_definition.get('operator', 'equals')
            value = segment_definition['value']
            
            if attribute_name == 'consent_state':
                # Direct field filter
                if operator == 'equals':
                    consent_value = ConsentState(value)
                    query = query.filter(User.consent_state == consent_value)
            else:
                # JSON attribute filter
                if operator == 'equals':
                    query = query.filter(User.attributes[attribute_name].astext == str(value))
                elif operator == 'contains':
                    query = query.filter(User.attributes[attribute_name].astext.ilike(f'%{value}%'))
        
        # Complex conditions with logic
        elif 'conditions' in segment_definition:
            conditions = segment_definition['conditions']
            logic = segment_definition.get('logic', 'AND')
            
            filters = []
            for condition in conditions:
                attribute_name = condition['attribute']
                operator = condition.get('operator', 'equals')
                value = condition['value']
                
                if operator == 'equals':
                    filters.append(User.attributes[attribute_name].astext == str(value))
                elif operator == 'contains':
                    filters.append(User.attributes[attribute_name].astext.ilike(f'%{value}%'))
            
            if logic == 'AND':
                query = query.filter(db.and_(*filters))
            elif logic == 'OR':
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
    
    # Get current time (using UTC for simplicity, could be enhanced with user timezone)
    current_time = datetime.utcnow().time()
    
    # Handle overnight quiet hours (e.g., 22:00 to 06:00)
    if start_time > end_time:
        return current_time >= start_time or current_time <= end_time
    else:
        return start_time <= current_time <= end_time


def render_message_template(template_content: str, user_attributes: Dict[str, Any]) -> str:
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
    placeholders = re.findall(r'\{(\w+)\}', template_content)
    
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


# Helper task to manually trigger a campaign (for API use)
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
            return {'error': f'Campaign {campaign_id} not found'}
        
        if campaign.status not in [CampaignStatus.READY, CampaignStatus.DRAFT]:
            return {'error': f'Campaign {campaign_id} is not ready for execution (status: {campaign.status})'}
        
        # Update status and queue execution
        campaign.status = CampaignStatus.RUNNING
        db.session.commit()
        
        # Queue the actual execution task
        task = run_campaign_task.delay(campaign_id)
        
        return {
            'campaign_id': campaign_id,
            'execution_task_id': task.id,
            'status': 'queued_for_execution',
            'queued_at': datetime.utcnow().isoformat()
        }