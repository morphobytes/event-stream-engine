"""
Integration tests for API endpoints
"""
import json
import pytest
from unittest.mock import patch, MagicMock


class TestWebhookAPI:
    """Test webhook processing endpoints"""
    
    def test_inbound_webhook_processing(self, client, sample_user):
        """Test inbound message webhook processing"""
        webhook_data = {
            'From': 'whatsapp:+15551234567',
            'To': 'whatsapp:+15551234568',
            'Body': 'Hello from user',
            'MessageSid': 'SM123456789',
            'WaId': '15551234567',
            'ProfileName': 'Test User'
        }
        
        response = client.post('/webhooks/inbound', 
                             data=webhook_data,
                             content_type='application/x-www-form-urlencoded')
        
        assert response.status_code == 200
        
    def test_status_webhook_processing(self, client, sample_message):
        """Test delivery status webhook processing"""
        webhook_data = {
            'MessageSid': sample_message.twilio_sid,
            'MessageStatus': 'delivered',
            'To': sample_message.phone_number
        }
        
        response = client.post('/webhooks/status',
                             data=webhook_data,
                             content_type='application/x-www-form-urlencoded')
        
        assert response.status_code == 200


class TestUserAPI:
    """Test user management API endpoints"""
    
    def test_create_user(self, client):
        """Test user creation endpoint"""
        user_data = {
            'phone_number': '+15559876543',
            'consent_status': 'opted_in',
            'attributes': {'name': 'New User', 'location': 'CA'}
        }
        
        response = client.post('/api/v1/users',
                             json=user_data,
                             content_type='application/json')
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['phone_number'] == '+15559876543'
        assert data['consent_status'] == 'opted_in'
    
    def test_get_user(self, client, sample_user):
        """Test getting user details"""
        response = client.get(f'/api/v1/users/{sample_user.phone_number}')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['phone_number'] == sample_user.phone_number
        assert data['consent_status'] == sample_user.consent_status
    
    def test_update_user_consent(self, client, sample_user):
        """Test updating user consent status"""
        consent_data = {'consent_status': 'opted_out'}
        
        response = client.put(f'/api/v1/users/{sample_user.phone_number}/consent',
                            json=consent_data,
                            content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['consent_status'] == 'opted_out'
    
    def test_bulk_user_upload_csv(self, client):
        """Test bulk user upload with CSV"""
        csv_data = "phone_number,name,location\n+15551111111,User1,US\n+15551111112,User2,CA"
        
        response = client.post('/api/v1/users/bulk',
                             data={'file': (BytesIO(csv_data.encode()), 'users.csv')},
                             content_type='multipart/form-data')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['processed'] == 2
        assert data['success'] == 2


class TestCampaignAPI:
    """Test campaign management API endpoints"""
    
    def test_create_campaign(self, client, sample_template):
        """Test campaign creation"""
        campaign_data = {
            'topic': 'New Test Campaign',
            'template_id': sample_template.id,
            'segment_query': {'consent_status': 'opted_in'},
            'rate_limit_per_second': 10,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '08:00'
        }
        
        response = client.post('/api/v1/campaigns',
                             json=campaign_data,
                             content_type='application/json')
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['topic'] == 'New Test Campaign'
        assert data['status'] == 'DRAFT'
    
    def test_get_campaign(self, client, sample_campaign):
        """Test getting campaign details"""
        response = client.get(f'/api/v1/campaigns/{sample_campaign.id}')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == sample_campaign.id
        assert data['topic'] == sample_campaign.topic
    
    @patch('app.runner.campaign_worker.run_campaign.delay')
    def test_trigger_campaign(self, mock_delay, client, sample_campaign):
        """Test triggering campaign execution"""
        mock_task = MagicMock()
        mock_task.id = 'test-task-123'
        mock_delay.return_value = mock_task
        
        response = client.post(f'/api/v1/campaigns/{sample_campaign.id}/trigger')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'triggered'
        assert 'task_id' in data
        mock_delay.assert_called_once()


class TestReportingAPI:
    """Test Phase 4.0 reporting endpoints"""
    
    def test_message_status_reporting(self, client, sample_message):
        """Test message status reporting endpoint"""
        response = client.get('/api/v1/reporting/messages/status?limit=10')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'messages' in data
        assert len(data['messages']) >= 0
    
    def test_campaign_summary_reporting(self, client, sample_campaign):
        """Test campaign summary reporting endpoint"""
        response = client.get(f'/api/v1/reporting/campaigns/{sample_campaign.id}/summary')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['campaign_id'] == sample_campaign.id
        assert 'total_recipients' in data
        assert 'messages_sent' in data
        assert 'success_rate_percent' in data
    
    def test_inbound_monitoring(self, client):
        """Test inbound events monitoring endpoint"""
        response = client.get('/api/v1/monitoring/inbound?limit=5')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'events' in data
    
    def test_dashboard_metrics(self, client):
        """Test dashboard metrics endpoint"""
        response = client.get('/api/v1/monitoring/dashboard')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'total_users' in data
        assert 'total_campaigns' in data
        assert 'messages_today' in data
        assert 'system_health' in data


class TestTemplateAPI:
    """Test template management endpoints"""
    
    def test_create_template(self, client):
        """Test template creation"""
        template_data = {
            'name': 'New Test Template',
            'content': 'Hello {name}, this is a test message!',
            'language': 'en'
        }
        
        response = client.post('/api/v1/templates',
                             json=template_data,
                             content_type='application/json')
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['name'] == 'New Test Template'
        assert data['is_active'] == True
    
    def test_get_templates(self, client, sample_template):
        """Test getting all templates"""
        response = client.get('/api/v1/templates')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'templates' in data
        assert len(data['templates']) >= 1


from io import BytesIO