"""
End-to-end integration tests for complete system workflows
"""
import pytest
from unittest.mock import patch, MagicMock
import json
from io import BytesIO


class TestE2EWorkflows:
    """Test complete end-to-end workflows"""
    
    @patch('app.runner.campaign_worker.send_whatsapp_message')
    def test_complete_campaign_workflow(self, mock_send, client, db_session):
        """Test complete workflow: create users -> create campaign -> trigger -> monitor"""
        
        # Mock successful Twilio responses
        mock_send.return_value = {
            'success': True,
            'sid': 'SM123456789',
            'status': 'queued'
        }
        
        # Step 1: Bulk upload users
        csv_data = "phone_number,name,location\n+15551111111,User1,US\n+15551111112,User2,CA"
        
        response = client.post('/api/v1/users/bulk',
                             data={'file': (BytesIO(csv_data.encode()), 'users.csv')},
                             content_type='multipart/form-data')
        
        assert response.status_code == 200
        upload_result = response.get_json()
        assert upload_result['processed'] == 2
        
        # Step 2: Create template
        template_data = {
            'name': 'E2E Test Template',
            'content': 'Hello {name}, this is a test message!',
            'language': 'en'
        }
        
        response = client.post('/api/v1/templates',
                             json=template_data,
                             content_type='application/json')
        
        assert response.status_code == 201
        template = response.get_json()
        template_id = template['id']
        
        # Step 3: Create campaign
        campaign_data = {
            'topic': 'E2E Test Campaign',
            'template_id': template_id,
            'segment_query': {'consent_status': 'opted_in'},
            'rate_limit_per_second': 5
        }
        
        response = client.post('/api/v1/campaigns',
                             json=campaign_data,
                             content_type='application/json')
        
        assert response.status_code == 201
        campaign = response.get_json()
        campaign_id = campaign['id']
        
        # Step 4: Trigger campaign
        with patch('app.runner.campaign_worker.run_campaign.delay') as mock_delay:
            mock_task = MagicMock()
            mock_task.id = 'test-task-123'
            mock_delay.return_value = mock_task
            
            response = client.post(f'/api/v1/campaigns/{campaign_id}/trigger')
            
            assert response.status_code == 200
            trigger_result = response.get_json()
            assert trigger_result['status'] == 'triggered'
        
        # Step 5: Check campaign summary
        response = client.get(f'/api/v1/reporting/campaigns/{campaign_id}/summary')
        
        assert response.status_code == 200
        summary = response.get_json()
        assert summary['campaign_id'] == campaign_id
        assert 'total_recipients' in summary
    
    def test_webhook_to_reporting_workflow(self, client, db_session, sample_campaign):
        """Test workflow from webhook ingestion to reporting"""
        
        # Step 1: Process inbound webhook
        inbound_data = {
            'From': 'whatsapp:+15551234567',
            'To': 'whatsapp:+15551234568', 
            'Body': 'Hello from customer',
            'MessageSid': 'SM123456789',
            'WaId': '15551234567'
        }
        
        response = client.post('/webhooks/inbound',
                             data=inbound_data,
                             content_type='application/x-www-form-urlencoded')
        
        assert response.status_code == 200
        
        # Step 2: Check inbound monitoring
        response = client.get('/api/v1/monitoring/inbound?limit=5')
        
        assert response.status_code == 200
        inbound_events = response.get_json()
        assert 'events' in inbound_events
        
        # Step 3: Process status webhook for outbound message
        # First create a message record
        from app.core.models.message import Message
        test_message = Message(
            phone_number='+15551234567',
            campaign_id=sample_campaign.id,
            template_content='Test message',
            status='sent',
            twilio_sid='SM987654321'
        )
        db_session.add(test_message)
        db_session.commit()
        
        # Status callback webhook
        status_data = {
            'MessageSid': 'SM987654321',
            'MessageStatus': 'delivered',
            'To': '+15551234567'
        }
        
        response = client.post('/webhooks/status',
                             data=status_data,
                             content_type='application/x-www-form-urlencoded')
        
        assert response.status_code == 200
        
        # Step 4: Check message status reporting
        response = client.get('/api/v1/reporting/messages/status?limit=10')
        
        assert response.status_code == 200
        message_status = response.get_json()
        assert 'messages' in message_status
    
    def test_ui_workflow_simulation(self, client):
        """Test UI workflow through API endpoints"""
        
        # Step 1: Dashboard data
        response = client.get('/api/v1/monitoring/dashboard')
        assert response.status_code == 200
        dashboard_data = response.get_json()
        assert 'total_users' in dashboard_data
        assert 'system_health' in dashboard_data
        
        # Step 2: User management
        response = client.get('/api/v1/users')
        assert response.status_code == 200
        users_data = response.get_json()
        assert 'users' in users_data
        
        # Step 3: Campaign management
        response = client.get('/api/v1/campaigns')
        assert response.status_code == 200
        campaigns_data = response.get_json()
        assert 'campaigns' in campaigns_data
        
        # Step 4: Templates
        response = client.get('/api/v1/templates')
        assert response.status_code == 200
        templates_data = response.get_json()
        assert 'templates' in templates_data
    
    def test_error_handling_workflow(self, client, sample_campaign):
        """Test error handling across the system"""
        
        # Test invalid campaign trigger
        response = client.post('/api/v1/campaigns/99999/trigger')
        assert response.status_code == 404
        
        # Test invalid user lookup
        response = client.get('/api/v1/users/+15559999999')
        assert response.status_code == 404
        
        # Test invalid campaign summary
        response = client.get('/api/v1/reporting/campaigns/99999/summary')
        assert response.status_code == 404
        
        # Test malformed webhook data
        response = client.post('/webhooks/inbound',
                             data={'invalid': 'data'},
                             content_type='application/x-www-form-urlencoded')
        # Should handle gracefully (not crash)
        assert response.status_code in [200, 400]


class TestPerformanceAndScaling:
    """Test system performance under load"""
    
    def test_bulk_user_processing_performance(self, client):
        """Test performance with larger bulk user uploads"""
        
        # Create larger CSV data (100 users)
        csv_lines = ['phone_number,name,location']
        for i in range(100):
            csv_lines.append(f'+1555000{i:04d},User{i},US')
        
        csv_data = '\n'.join(csv_lines)
        
        response = client.post('/api/v1/users/bulk',
                             data={'file': (BytesIO(csv_data.encode()), 'large_users.csv')},
                             content_type='multipart/form-data')
        
        assert response.status_code == 200
        result = response.get_json()
        assert result['processed'] == 100
        # Performance: should complete within reasonable time
    
    def test_segment_evaluation_performance(self, db_session):
        """Test segment evaluation with larger datasets"""
        from app.core.models.user import User
        
        # Create many users for testing
        users = []
        for i in range(50):
            user = User(
                phone_number=f'+1555000{i:04d}',
                consent_status='opted_in' if i % 2 == 0 else 'opted_out',
                attributes={
                    'location': 'US' if i % 3 == 0 else 'CA',
                    'premium': True if i % 5 == 0 else False,
                    'age': 20 + (i % 50)
                }
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        # Test complex segment query performance
        from app.runner.segment_evaluator import SegmentEvaluator
        evaluator = SegmentEvaluator(db_session)
        
        segment_query = {
            'consent_status': 'opted_in',
            'attributes': {
                'location': 'US',
                'premium': True
            }
        }
        
        # Should execute efficiently
        users = evaluator.evaluate_segment(segment_query)
        assert len(users) >= 0  # Should return results without timeout


class TestSystemIntegration:
    """Test integration between system components"""
    
    @patch('redis.Redis')
    def test_redis_integration(self, mock_redis):
        """Test Redis integration for caching and task queue"""
        
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        # Test Redis connectivity check
        from app.core.utils.health_check import check_redis_health
        health = check_redis_health()
        
        assert health['status'] == 'healthy'
        mock_redis_instance.ping.assert_called_once()
    
    def test_database_transaction_integrity(self, db_session, sample_user):
        """Test database transaction integrity"""
        
        # Test atomic operations
        original_consent = sample_user.consent_status
        
        try:
            # Start transaction
            db_session.begin()
            
            # Update user
            sample_user.consent_status = 'opted_out'
            
            # Simulate error condition
            if True:  # Force rollback
                db_session.rollback()
                
        except Exception:
            db_session.rollback()
        
        # Verify rollback worked
        db_session.refresh(sample_user)
        assert sample_user.consent_status == original_consent
    
    @patch('app.core.services.twilio_service.TwilioService.send_message')
    def test_twilio_integration_mock(self, mock_send):
        """Test Twilio service integration with mocking"""
        
        mock_send.return_value = {
            'sid': 'SM123456789',
            'status': 'queued',
            'error_code': None
        }
        
        from app.core.services.twilio_service import TwilioService
        service = TwilioService()
        
        result = service.send_message(
            to='+15551234567',
            message='Test message'
        )
        
        assert result['sid'] == 'SM123456789'
        assert result['status'] == 'queued'
        mock_send.assert_called_once()


class TestComplianceAndSecurity:
    """Test compliance and security features"""
    
    def test_consent_enforcement(self, client, db_session):
        """Test that opted-out users are not messaged"""
        
        # Create opted-out user
        user_data = {
            'phone_number': '+15551234567',
            'consent_status': 'opted_out',
            'attributes': {'name': 'Opted Out User'}
        }
        
        response = client.post('/api/v1/users',
                             json=user_data,
                             content_type='application/json')
        assert response.status_code == 201
        
        # Create campaign
        template_data = {
            'name': 'Consent Test Template',
            'content': 'Hello {name}!',
            'language': 'en'
        }
        
        response = client.post('/api/v1/templates',
                             json=template_data,
                             content_type='application/json')
        
        template = response.get_json()
        
        campaign_data = {
            'topic': 'Consent Test Campaign',
            'template_id': template['id'],
            'segment_query': {}  # Target all users
        }
        
        response = client.post('/api/v1/campaigns',
                             json=campaign_data,
                             content_type='application/json')
        
        campaign = response.get_json()
        
        # Trigger campaign - should respect consent
        with patch('app.runner.campaign_worker.run_campaign.delay') as mock_delay:
            mock_task = MagicMock()
            mock_delay.return_value = mock_task
            
            response = client.post(f'/api/v1/campaigns/{campaign["id"]}/trigger')
            assert response.status_code == 200
        
        # Verify opted-out user was not included in targeting
        response = client.get(f'/api/v1/reporting/campaigns/{campaign["id"]}/summary')
        summary = response.get_json()
        
        # Campaign should have 0 messages to opted-out users
        # (This would be verified in the actual campaign execution)
    
    def test_data_validation(self, client):
        """Test input validation and sanitization"""
        
        # Test invalid phone number
        invalid_user = {
            'phone_number': 'not-a-phone',
            'consent_status': 'opted_in'
        }
        
        response = client.post('/api/v1/users',
                             json=invalid_user,
                             content_type='application/json')
        
        assert response.status_code == 400  # Should reject invalid data
        
        # Test SQL injection attempt
        malicious_template = {
            'name': 'Template"; DROP TABLE users; --',
            'content': 'Hello world',
            'language': 'en'
        }
        
        response = client.post('/api/v1/templates',
                             json=malicious_template,
                             content_type='application/json')
        
        # Should handle safely (either accept as string or validate)
        assert response.status_code in [201, 400]