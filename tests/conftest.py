"""
Test configuration and fixtures for Event Stream Engine
"""
import os
import pytest
import tempfile
from app.main import create_app
from app.core.models import db
from app.core.models.user import User
from app.core.models.template import Template
from app.core.models.campaign import Campaign
from app.core.models.message import Message


@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app({
        'TESTING': True,
        'DATABASE_URL': f'sqlite:///{db_path}',
        'REDIS_URL': 'redis://localhost:6379/15',  # Use test database
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'TWILIO_ACCOUNT_SID': 'test_account_sid',
        'TWILIO_AUTH_TOKEN': 'test_auth_token',
        'TWILIO_PHONE_NUMBER': 'whatsapp:+15551234567'
    })
    
    with app.app_context():
        db.create_all()
        yield app
        
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner"""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Create database session for tests"""
    with app.app_context():
        # Clean up any existing data
        db.session.query(Message).delete()
        db.session.query(Campaign).delete()
        db.session.query(Template).delete()
        db.session.query(User).delete()
        db.session.commit()
        
        yield db.session
        
        # Cleanup after test
        db.session.rollback()


@pytest.fixture
def sample_user(db_session):
    """Create sample user for testing"""
    user = User(
        phone_number='+15551234567',
        consent_status='opted_in',
        attributes={'name': 'Test User', 'location': 'US'}
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_template(db_session):
    """Create sample template for testing"""
    template = Template(
        name='Welcome Template',
        content='Hello {name}, welcome to our service!',
        language='en',
        is_active=True
    )
    db_session.add(template)
    db_session.commit()
    return template


@pytest.fixture
def sample_campaign(db_session, sample_template):
    """Create sample campaign for testing"""
    campaign = Campaign(
        topic='Test Campaign',
        template_id=sample_template.id,
        segment_query={'consent_status': 'opted_in'},
        status='DRAFT',
        rate_limit_per_second=5,
        quiet_hours_start='22:00',
        quiet_hours_end='08:00'
    )
    db_session.add(campaign)
    db_session.commit()
    return campaign


@pytest.fixture
def sample_message(db_session, sample_user, sample_campaign):
    """Create sample message for testing"""
    message = Message(
        phone_number=sample_user.phone_number,
        campaign_id=sample_campaign.id,
        template_content='Hello Test User, welcome to our service!',
        status='sent',
        twilio_sid='SM123456789',
        created_at=db.func.now(),
        sent_at=db.func.now()
    )
    db_session.add(message)
    db_session.commit()
    return message