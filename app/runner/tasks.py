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
from app.core.data_model import User, Campaign, Segment, ConsentState


def get_flask_app():
    """Get Flask app context for database operations"""
    return create_app()


@celery_app.task(bind=True, max_retries=3)
def bulk_ingest_users(self, file_path: str, file_format: str = 'csv') -> Dict[str, Any]:
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
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'duplicates_merged': 0,
                'errors': [],
                'started_at': datetime.utcnow().isoformat(),
                'file_path': file_path
            }
            
            # Validate file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Process based on file format
            if file_format.lower() == 'csv':
                records = _process_csv_file(file_path)
            elif file_format.lower() in ['json', 'jsonl']:
                records = _process_json_file(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_format}")
            
            # Process each record
            for record in records:
                results['total_processed'] += 1
                
                try:
                    # Validate and process user record
                    processed_user = _process_user_record(record, results['total_processed'])
                    
                    if processed_user:
                        # Perform upsert operation
                        user_result = _upsert_user(processed_user)
                        
                        if user_result['action'] == 'created':
                            results['successful'] += 1
                        elif user_result['action'] == 'merged':
                            results['duplicates_merged'] += 1
                            results['successful'] += 1
                        
                except Exception as record_error:
                    results['failed'] += 1
                    results['errors'].append({
                        'record_number': results['total_processed'],
                        'error': str(record_error),
                        'record_data': record
                    })
                    
                    # Continue processing other records
                    continue
            
            # Commit all changes
            db.session.commit()
            
            results['completed_at'] = datetime.utcnow().isoformat()
            
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
                'total_processed': results.get('total_processed', 0),
                'successful': 0,
                'failed': results.get('total_processed', 0),
                'duplicates_merged': 0,
                'errors': [{'error': f'Task failed: {str(e)}'}],
                'completed_at': datetime.utcnow().isoformat()
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
                'event_id': event_payload.get('event_id'),
                'processed_at': datetime.utcnow().isoformat(),
                'status': 'processing'
            }
            
            # Parse and validate event payload
            event_type = event_payload.get('type')
            campaign_id = event_payload.get('campaign_id')
            segment_id = event_payload.get('segment_id')
            
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
                results['campaign_topic'] = campaign.topic
                results['template_id'] = campaign.template_id
                
                # TODO: Queue actual campaign execution task
                # execute_campaign.delay(campaign.id, segment.id if segment else None, event_payload)
                
                results['status'] = 'queued_for_execution'
            else:
                results['status'] = 'validated_no_campaign'
            
            if segment:
                results['segment_name'] = segment.name
                results['segment_definition'] = segment.definition_json
            
            return results
            
        except Exception as e:
            # Retry logic for transient failures
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=30, exc=e)
            
            return {
                'event_id': event_payload.get('event_id'),
                'processed_at': datetime.utcnow().isoformat(),
                'status': 'failed',
                'error': str(e)
            }


def _process_csv_file(file_path: str):
    """Process CSV file and yield records"""
    with open(file_path, 'r', encoding='utf-8') as csvfile:
        # Detect delimiter
        sample = csvfile.read(1024)
        csvfile.seek(0)
        delimiter = ',' if ',' in sample else ';'
        
        reader = csv.DictReader(csvfile, delimiter=delimiter)
        for row in reader:
            yield row


def _process_json_file(file_path: str):
    """Process JSON/JSONL file and yield records"""
    with open(file_path, 'r', encoding='utf-8') as jsonfile:
        content = jsonfile.read().strip()
        
        # Handle both JSON array and JSONL formats
        if content.startswith('['):
            # JSON array format
            data = json.loads(content)
            for record in data:
                yield record
        else:
            # JSONL format (one JSON object per line)
            for line in content.split('\n'):
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
    phone_raw = record.get('phone', record.get('phone_e164', record.get('phone_number')))
    if not phone_raw:
        raise ValueError(f"Missing phone number in record {record_number}")
    
    # Remove channel prefixes (whatsapp:, sms:, etc.)
    phone_cleaned = re.sub(r'^(whatsapp:|sms:|messenger:|voice:)', '', str(phone_raw).strip())
    
    # Validate E.164 format
    if not re.match(r'^\+[1-9]\d{1,14}$', phone_cleaned):
        raise ValueError(f"Invalid E.164 phone format: {phone_cleaned}")
    
    # Extract consent state
    consent_raw = record.get('consent_state', record.get('consent', 'OPT_IN'))
    try:
        consent_state = ConsentState(consent_raw.upper())
    except ValueError:
        consent_state = ConsentState.OPT_IN  # Default to OPT_IN
    
    # Extract and clean attributes
    attributes = {}
    for key, value in record.items():
        if key not in ['phone', 'phone_e164', 'phone_number', 'consent_state', 'consent']:
            if value is not None and str(value).strip():
                attributes[key] = str(value).strip()
    
    return {
        'phone_e164': phone_cleaned,
        'consent_state': consent_state,
        'attributes': attributes
    }


def _upsert_user(user_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Perform upsert operation for user with attribute merging
    
    Args:
        user_data: Processed user data
        
    Returns:
        Dict with action taken ('created' or 'merged')
    """
    phone_e164 = user_data['phone_e164']
    
    # Check if user exists
    existing_user = User.query.get(phone_e164)
    
    if existing_user:
        # Merge attributes (new attributes override existing ones)
        merged_attributes = existing_user.attributes.copy() if existing_user.attributes else {}
        merged_attributes.update(user_data['attributes'])
        
        # Update existing user
        existing_user.attributes = merged_attributes
        existing_user.consent_state = user_data['consent_state']
        existing_user.updated_at = datetime.utcnow()
        
        return {'action': 'merged', 'phone': phone_e164}
    else:
        # Create new user
        new_user = User(
            phone_e164=phone_e164,
            attributes=user_data['attributes'],
            consent_state=user_data['consent_state']
        )
        
        db.session.add(new_user)
        return {'action': 'created', 'phone': phone_e164}