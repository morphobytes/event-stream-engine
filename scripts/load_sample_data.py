"""
Sample data loader for Event Stream Engine
Creates initial templates, segments, and test data
"""
from app.main import create_app, db
from app.core.data_model import User, Template, Segment, ConsentState
import json

def load_sample_data():
    """Load sample templates and segments for API testing"""
    
    # Sample templates
    templates = [
        {
            'name': 'welcome_message',
            'channel': 'whatsapp',
            'locale': 'en_US',
            'content': 'Welcome to Event Stream Engine! Thank you for joining, {profile_name}.'
        },
        {
            'name': 'price_alert',
            'channel': 'whatsapp', 
            'locale': 'en_US',
            'content': 'Price Alert: {product_name} is now available for ${price}! Limited time offer.'
        },
        {
            'name': 'reminder_message',
            'channel': 'whatsapp',
            'locale': 'en_US',
            'content': 'Reminder: You have an upcoming appointment on {appointment_date}. Reply CONFIRM to confirm.'
        }
    ]
    
    # Sample segments  
    segments = [
        {
            'name': 'opted_in_users',
            'definition_json': {
                'attribute': 'consent_state',
                'operator': 'equals',
                'value': 'OPT_IN'
            }
        },
        {
            'name': 'colombo_users',
            'definition_json': {
                'conditions': [
                    {'attribute': 'city', 'operator': 'equals', 'value': 'Colombo'},
                    {'attribute': 'consent_state', 'operator': 'equals', 'value': 'OPT_IN'}
                ],
                'logic': 'AND'
            }
        },
        {
            'name': 'premium_subscribers',
            'definition_json': {
                'conditions': [
                    {'attribute': 'subscription_tier', 'operator': 'equals', 'value': 'premium'},
                    {'attribute': 'consent_state', 'operator': 'not_equals', 'value': 'STOP'}
                ],
                'logic': 'AND'
            }
        }
    ]
    
    # Sample users
    users = [
        {
            'phone_e164': '+94771234567',
            'consent_state': ConsentState.OPT_IN,
            'attributes': {
                'profile_name': 'John Doe',
                'city': 'Colombo',
                'subscription_tier': 'premium',
                'language': 'en'
            }
        },
        {
            'phone_e164': '+94771234568', 
            'consent_state': ConsentState.OPT_IN,
            'attributes': {
                'profile_name': 'Jane Smith',
                'city': 'Kandy',
                'subscription_tier': 'basic',
                'language': 'en'
            }
        },
        {
            'phone_e164': '+94771234569',
            'consent_state': ConsentState.STOP,
            'attributes': {
                'profile_name': 'Bob Wilson',
                'city': 'Colombo',
                'subscription_tier': 'basic'
            }
        }
    ]
    
    print("Loading sample templates...")
    for template_data in templates:
        existing = Template.query.filter_by(name=template_data['name']).first()
        if not existing:
            template = Template(**template_data)
            db.session.add(template)
            print(f"Created template: {template_data['name']}")
    
    print("Loading sample segments...")  
    for segment_data in segments:
        existing = Segment.query.filter_by(name=segment_data['name']).first()
        if not existing:
            segment = Segment(**segment_data)
            db.session.add(segment)
            print(f"Created segment: {segment_data['name']}")
    
    print("Loading sample users...")
    for user_data in users:
        existing = User.query.get(user_data['phone_e164'])
        if not existing:
            user = User(**user_data)
            db.session.add(user)
            print(f"Created user: {user_data['phone_e164']}")
    
    db.session.commit()
    print("Sample data loaded successfully!")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        load_sample_data()