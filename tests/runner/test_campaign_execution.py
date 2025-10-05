"""
Integration tests for campaign orchestration and runner
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from app.runner.campaign_worker import CampaignWorker
from app.ingestion.file_processor import FileProcessor
import tempfile
import csv
import json


class TestCampaignOrchestration:
    """Test complete campaign execution workflow"""
    
    @patch('app.runner.campaign_worker.send_whatsapp_message')
    def test_campaign_execution_flow(self, mock_send, db_session, sample_campaign, sample_user):
        """Test complete campaign execution from trigger to delivery"""
        worker = CampaignWorker(db_session)
        
        # Mock successful Twilio send
        mock_send.return_value = {
            'success': True,
            'sid': 'SM123456789',
            'status': 'queued'
        }
        
        # Ensure user is eligible for campaign
        sample_user.consent_status = 'opted_in'
        sample_campaign.status = 'READY'
        db_session.commit()
        
        # Execute campaign
        result = worker.execute_campaign(sample_campaign.id)
        
        assert result['status'] == 'success'
        assert result['messages_sent'] > 0
        mock_send.assert_called()
    
    def test_segment_targeting(self, db_session, sample_campaign):
        """Test campaign targeting specific user segments"""
        from app.core.models.user import User
        
        # Create users with different attributes
        user1 = User(
            phone_number='+15551111111',
            consent_status='opted_in',
            attributes={'location': 'US', 'premium': True}
        )
        user2 = User(
            phone_number='+15551111112', 
            consent_status='opted_in',
            attributes={'location': 'CA', 'premium': False}
        )
        user3 = User(
            phone_number='+15551111113',
            consent_status='opted_out',  # Should be excluded
            attributes={'location': 'US', 'premium': True}
        )
        
        db_session.add_all([user1, user2, user3])
        db_session.commit()
        
        # Campaign targeting US premium users who are opted in
        sample_campaign.segment_query = {
            'consent_status': 'opted_in',
            'attributes': {'location': 'US', 'premium': True}
        }
        db_session.commit()
        
        worker = CampaignWorker(db_session)
        eligible_users = worker.get_eligible_users(sample_campaign.id)
        
        # Only user1 should match the segment
        eligible_phones = [u.phone_number for u in eligible_users]
        assert '+15551111111' in eligible_phones
        assert '+15551111112' not in eligible_phones  # Wrong location/premium combo
        assert '+15551111113' not in eligible_phones  # Opted out
    
    def test_rate_limiting(self, db_session, sample_campaign):
        """Test campaign rate limiting functionality"""
        from app.core.models.user import User
        
        # Create multiple users
        users = []
        for i in range(5):
            user = User(
                phone_number=f'+155511111{i:02d}',
                consent_status='opted_in'
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        # Set low rate limit
        sample_campaign.rate_limit_per_second = 2
        sample_campaign.status = 'READY'
        db_session.commit()
        
        worker = CampaignWorker(db_session)
        
        # Mock time tracking for rate limiting
        with patch('time.sleep') as mock_sleep:
            with patch('app.runner.campaign_worker.send_whatsapp_message') as mock_send:
                mock_send.return_value = {
                    'success': True,
                    'sid': 'SM123456789',
                    'status': 'queued'
                }
                
                result = worker.execute_campaign(sample_campaign.id)
                
                # Should have applied rate limiting (sleep called between batches)
                assert mock_sleep.called
    
    def test_quiet_hours_enforcement(self, db_session, sample_campaign, sample_user):
        """Test quiet hours enforcement in campaigns"""
        worker = CampaignWorker(db_session)
        
        # Set quiet hours (22:00 to 08:00)
        sample_campaign.quiet_hours_start = '22:00'
        sample_campaign.quiet_hours_end = '08:00'
        db_session.commit()
        
        # Test during quiet hours (23:00)
        with patch('app.runner.campaign_worker.get_current_time_for_user') as mock_time:
            mock_time.return_value = datetime(2024, 1, 1, 23, 0)  # 11 PM
            
            is_quiet = worker.is_quiet_hours(sample_user.phone_number, sample_campaign)
            assert is_quiet is True
        
        # Test during active hours (14:00)
        with patch('app.runner.campaign_worker.get_current_time_for_user') as mock_time:
            mock_time.return_value = datetime(2024, 1, 1, 14, 0)  # 2 PM
            
            is_quiet = worker.is_quiet_hours(sample_user.phone_number, sample_campaign)
            assert is_quiet is False
    
    @patch('app.runner.campaign_worker.send_whatsapp_message')
    def test_template_rendering_in_campaign(self, mock_send, db_session, sample_campaign, sample_user, sample_template):
        """Test template rendering during campaign execution"""
        mock_send.return_value = {
            'success': True,
            'sid': 'SM123456789',
            'status': 'queued'
        }
        
        # Set user attributes for template rendering
        sample_user.attributes = {'name': 'Test User'}
        sample_user.consent_status = 'opted_in'
        
        # Template content: "Hello {name}, welcome to our service!"
        sample_template.content = 'Hello {name}, welcome to our service!'
        
        sample_campaign.status = 'READY'
        db_session.commit()
        
        worker = CampaignWorker(db_session)
        result = worker.execute_campaign(sample_campaign.id)
        
        # Verify template was rendered with user data
        assert result['status'] == 'success'
        
        # Check that send was called with rendered content
        call_args = mock_send.call_args[1]  # Get keyword arguments
        assert 'Test User' in call_args['message_content']
    
    def test_campaign_error_handling(self, db_session, sample_campaign, sample_user):
        """Test error handling during campaign execution"""
        worker = CampaignWorker(db_session)
        
        # Mock Twilio API failure
        with patch('app.runner.campaign_worker.send_whatsapp_message') as mock_send:
            mock_send.return_value = {
                'success': False,
                'error': 'Invalid phone number',
                'error_code': '21211'
            }
            
            sample_user.consent_status = 'opted_in'
            sample_campaign.status = 'READY'
            db_session.commit()
            
            result = worker.execute_campaign(sample_campaign.id)
            
            # Campaign should handle errors gracefully
            assert 'errors' in result
            assert result['messages_failed'] > 0


class TestFileProcessing:
    """Test bulk file processing and ingestion"""
    
    def test_csv_user_import(self, db_session):
        """Test CSV file processing for user import"""
        processor = FileProcessor(db_session)
        
        # Create temporary CSV file
        csv_data = [
            ['phone_number', 'name', 'location', 'premium'],
            ['+15551234567', 'John Doe', 'US', 'true'],
            ['+15551234568', 'Jane Smith', 'CA', 'false'],
            ['+44207123456', 'Bob Johnson', 'UK', 'true']
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
            temp_path = f.name
        
        try:
            # Process the CSV file
            result = processor.process_csv_file(temp_path)
            
            assert result['success'] is True
            assert result['processed'] == 3
            assert result['created'] == 3
            assert result['updated'] == 0
            
            # Verify users were created in database
            from app.core.models.user import User
            users = db_session.query(User).all()
            assert len(users) >= 3
            
            # Check specific user data
            john = db_session.query(User).filter_by(phone_number='+15551234567').first()
            assert john is not None
            assert john.attributes['name'] == 'John Doe'
            assert john.attributes['location'] == 'US'
            assert john.attributes['premium'] == 'true'
            
        finally:
            import os
            os.unlink(temp_path)
    
    def test_json_user_import(self, db_session):
        """Test JSON file processing for user import"""
        processor = FileProcessor(db_session)
        
        # Create temporary JSON file
        json_data = [
            {
                'phone_number': '+15559876543',
                'name': 'Alice Wilson',
                'location': 'US',
                'subscription_tier': 'premium',
                'join_date': '2024-01-15'
            },
            {
                'phone_number': '+15559876544',
                'name': 'Charlie Brown',
                'location': 'CA',
                'subscription_tier': 'basic',
                'join_date': '2024-01-20'
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(json_data, f)
            temp_path = f.name
        
        try:
            # Process the JSON file
            result = processor.process_json_file(temp_path)
            
            assert result['success'] is True
            assert result['processed'] == 2
            assert result['created'] == 2
            
            # Verify users were created
            from app.core.models.user import User
            alice = db_session.query(User).filter_by(phone_number='+15559876543').first()
            assert alice is not None
            assert alice.attributes['name'] == 'Alice Wilson'
            assert alice.attributes['subscription_tier'] == 'premium'
            
        finally:
            import os
            os.unlink(temp_path)
    
    def test_duplicate_handling_in_import(self, db_session):
        """Test handling of duplicate users during import"""
        processor = FileProcessor(db_session)
        
        # Create initial user
        from app.core.models.user import User
        existing_user = User(
            phone_number='+15551234567',
            consent_status='opted_in',
            attributes={'name': 'Original Name', 'location': 'US'}
        )
        db_session.add(existing_user)
        db_session.commit()
        
        # Import CSV with same phone number but different data
        csv_data = [
            ['phone_number', 'name', 'location'],
            ['+15551234567', 'Updated Name', 'CA'],  # Same phone, different data
            ['+15551234568', 'New User', 'UK']  # New phone number
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
            temp_path = f.name
        
        try:
            result = processor.process_csv_file(temp_path)
            
            assert result['success'] is True
            assert result['processed'] == 2
            assert result['created'] == 1  # Only one new user
            assert result['updated'] == 1  # One existing user updated
            
            # Verify the existing user was updated
            updated_user = db_session.query(User).filter_by(phone_number='+15551234567').first()
            assert updated_user.attributes['name'] == 'Updated Name'
            assert updated_user.attributes['location'] == 'CA'
            
        finally:
            import os
            os.unlink(temp_path)
    
    def test_invalid_phone_number_handling(self, db_session):
        """Test handling of invalid phone numbers during import"""
        processor = FileProcessor(db_session)
        
        # CSV with invalid phone numbers
        csv_data = [
            ['phone_number', 'name', 'location'],
            ['+15551234567', 'Valid User', 'US'],  # Valid
            ['1234567890', 'Invalid Format', 'CA'],  # Missing +
            ['not-a-phone', 'Invalid Phone', 'UK'],  # Not a phone number
            ['+999123456789012345', 'Too Long', 'DE'],  # Too long
            ['+15551234568', 'Another Valid', 'FR']  # Valid
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
            temp_path = f.name
        
        try:
            result = processor.process_csv_file(temp_path)
            
            # Should process file but skip invalid entries
            assert result['success'] is True
            assert result['processed'] == 5  # All rows processed
            assert result['created'] == 2   # Only valid phone numbers created
            assert len(result.get('errors', [])) >= 3  # Errors for invalid numbers
            
        finally:
            import os
            os.unlink(temp_path)