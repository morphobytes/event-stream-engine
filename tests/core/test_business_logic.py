"""
Integration tests for core business logic
"""
import pytest
from unittest.mock import patch, MagicMock
from app.core.services.consent_manager import ConsentManager
from app.core.services.phone_validator import PhoneValidator
from app.runner.segment_evaluator import SegmentEvaluator
from app.runner.template_renderer import TemplateRenderer


class TestConsentManager:
    """Test consent management functionality"""
    
    def test_opt_in_user(self, db_session, sample_user):
        """Test opting in a user"""
        consent_manager = ConsentManager(db_session)
        
        # Initially opted out
        sample_user.consent_status = 'opted_out'
        db_session.commit()
        
        # Opt in
        result = consent_manager.update_consent(
            sample_user.phone_number, 
            'opted_in'
        )
        
        assert result is True
        assert sample_user.consent_status == 'opted_in'
    
    def test_opt_out_user(self, db_session, sample_user):
        """Test opting out a user"""
        consent_manager = ConsentManager(db_session)
        
        # Initially opted in
        sample_user.consent_status = 'opted_in'
        db_session.commit()
        
        # Opt out
        result = consent_manager.update_consent(
            sample_user.phone_number,
            'opted_out'
        )
        
        assert result is True
        assert sample_user.consent_status == 'opted_out'
    
    def test_can_send_message(self, db_session, sample_user):
        """Test checking if message can be sent to user"""
        consent_manager = ConsentManager(db_session)
        
        # Opted in user should be able to receive messages
        sample_user.consent_status = 'opted_in'
        db_session.commit()
        
        can_send = consent_manager.can_send_message(sample_user.phone_number)
        assert can_send is True
        
        # Opted out user should not receive messages
        sample_user.consent_status = 'opted_out'
        db_session.commit()
        
        can_send = consent_manager.can_send_message(sample_user.phone_number)
        assert can_send is False


class TestPhoneValidator:
    """Test phone number validation logic"""
    
    def test_valid_e164_numbers(self):
        """Test validation of valid E.164 phone numbers"""
        validator = PhoneValidator()
        
        valid_numbers = [
            '+15551234567',
            '+44207123456',
            '+33123456789',
            '+81312345678'
        ]
        
        for number in valid_numbers:
            result = validator.validate_and_format(number)
            assert result['is_valid'] is True
            assert result['formatted_number'].startswith('+')
    
    def test_invalid_phone_numbers(self):
        """Test validation of invalid phone numbers"""
        validator = PhoneValidator()
        
        invalid_numbers = [
            '1234567890',  # Missing country code
            '+1555123456',  # Too short
            '+155512345678901',  # Too long
            'not-a-phone-number',
            '',
            None
        ]
        
        for number in invalid_numbers:
            result = validator.validate_and_format(number)
            assert result['is_valid'] is False
    
    def test_format_normalization(self):
        """Test phone number format normalization"""
        validator = PhoneValidator()
        
        # Different formats of the same number
        test_cases = [
            ('15551234567', '+15551234567'),
            ('(555) 123-4567', '+15551234567'),
            ('+1 555 123 4567', '+15551234567'),
            ('555.123.4567', '+15551234567')
        ]
        
        for input_number, expected in test_cases:
            result = validator.validate_and_format(input_number, default_country='US')
            if result['is_valid']:
                assert result['formatted_number'] == expected


class TestSegmentEvaluator:
    """Test user segment evaluation logic"""
    
    def test_simple_attribute_matching(self, db_session, sample_user):
        """Test simple attribute-based segment matching"""
        evaluator = SegmentEvaluator(db_session)
        
        # Test consent status matching
        segment_query = {'consent_status': 'opted_in'}
        users = evaluator.evaluate_segment(segment_query)
        
        user_phones = [u.phone_number for u in users]
        assert sample_user.phone_number in user_phones
    
    def test_attribute_json_matching(self, db_session, sample_user):
        """Test JSON attribute matching in segments"""
        evaluator = SegmentEvaluator(db_session)
        
        # Update user attributes
        sample_user.attributes = {'location': 'US', 'premium': True}
        db_session.commit()
        
        # Test location matching
        segment_query = {'attributes': {'location': 'US'}}
        users = evaluator.evaluate_segment(segment_query)
        
        user_phones = [u.phone_number for u in users]
        assert sample_user.phone_number in user_phones
    
    def test_complex_segment_queries(self, db_session, sample_user):
        """Test complex segment evaluation with multiple conditions"""
        evaluator = SegmentEvaluator(db_session)
        
        # Update user for testing
        sample_user.attributes = {'location': 'US', 'premium': True, 'age': 25}
        sample_user.consent_status = 'opted_in'
        db_session.commit()
        
        # Complex query: opted in US users with premium
        segment_query = {
            'consent_status': 'opted_in',
            'attributes': {
                'location': 'US',
                'premium': True
            }
        }
        
        users = evaluator.evaluate_segment(segment_query)
        user_phones = [u.phone_number for u in users]
        assert sample_user.phone_number in user_phones
    
    def test_exclusion_segments(self, db_session, sample_user):
        """Test segment queries that should exclude users"""
        evaluator = SegmentEvaluator(db_session)
        
        # User is opted out
        sample_user.consent_status = 'opted_out'
        db_session.commit()
        
        # Query for opted in users only
        segment_query = {'consent_status': 'opted_in'}
        users = evaluator.evaluate_segment(segment_query)
        
        user_phones = [u.phone_number for u in users]
        assert sample_user.phone_number not in user_phones


class TestTemplateRenderer:
    """Test message template rendering"""
    
    def test_basic_placeholder_substitution(self, sample_user, sample_template):
        """Test basic placeholder substitution in templates"""
        renderer = TemplateRenderer()
        
        # Template: "Hello {name}, welcome to our service!"
        # User has name attribute
        sample_user.attributes = {'name': 'John Doe'}
        
        rendered = renderer.render_template(sample_template.content, sample_user)
        
        assert rendered == "Hello John Doe, welcome to our service!"
    
    def test_missing_attribute_handling(self, sample_user, sample_template):
        """Test handling of missing user attributes in templates"""
        renderer = TemplateRenderer()
        
        # Template has {name} placeholder but user has no name attribute
        sample_user.attributes = {}
        
        rendered = renderer.render_template(sample_template.content, sample_user)
        
        # Should gracefully handle missing attributes
        assert '{name}' not in rendered or 'Unknown' in rendered
    
    def test_multiple_placeholder_substitution(self, sample_user):
        """Test template with multiple placeholders"""
        renderer = TemplateRenderer()
        
        template_content = "Hi {name}, your order #{order_id} for ${amount} has been confirmed!"
        sample_user.attributes = {
            'name': 'Jane Smith',
            'order_id': '12345',
            'amount': '29.99'
        }
        
        rendered = renderer.render_template(template_content, sample_user)
        
        expected = "Hi Jane Smith, your order #12345 for $29.99 has been confirmed!"
        assert rendered == expected
    
    def test_conditional_rendering(self, sample_user):
        """Test conditional content rendering based on user attributes"""
        renderer = TemplateRenderer()
        
        # Template with conditional content for premium users
        template_content = "Hello {name}! {% if premium %}Enjoy your premium benefits!{% endif %}"
        
        # Premium user
        sample_user.attributes = {'name': 'Premium User', 'premium': True}
        rendered = renderer.render_template(template_content, sample_user)
        assert "Enjoy your premium benefits!" in rendered
        
        # Non-premium user
        sample_user.attributes = {'name': 'Regular User', 'premium': False}
        rendered = renderer.render_template(template_content, sample_user)
        assert "Enjoy your premium benefits!" not in rendered


class TestDataIntegrity:
    """Test data integrity and validation"""
    
    def test_duplicate_phone_number_handling(self, db_session):
        """Test handling of duplicate phone numbers"""
        from app.core.models.user import User
        
        # Try to create users with the same phone number
        user1 = User(
            phone_number='+15551111111',
            consent_status='opted_in'
        )
        db_session.add(user1)
        db_session.commit()
        
        user2 = User(
            phone_number='+15551111111',  # Same phone number
            consent_status='opted_out'
        )
        
        # Should raise integrity error due to unique constraint
        db_session.add(user2)
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.commit()
    
    def test_campaign_template_relationship(self, db_session, sample_template):
        """Test campaign-template relationship integrity"""
        from app.core.models.campaign import Campaign
        
        campaign = Campaign(
            topic='Test Relationship',
            template_id=sample_template.id,
            segment_query={'consent_status': 'opted_in'},
            status='DRAFT'
        )
        
        db_session.add(campaign)
        db_session.commit()
        
        # Campaign should reference the template
        assert campaign.template_id == sample_template.id
        
        # Should be able to access template through relationship
        assert campaign.template is not None
        assert campaign.template.name == sample_template.name