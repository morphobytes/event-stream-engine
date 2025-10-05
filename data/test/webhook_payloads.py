"""
Sample webhook payloads for testing Twilio integrations
"""

# Inbound message webhook payload
INBOUND_MESSAGE_WEBHOOK = {
    "MessageSid": "SMtestmessageid1234567890abcdef12",
    "AccountSid": "ACtestaccountid1234567890abcdef12",
    "MessagingServiceSid": "MGtestserviceid1234567890abcdef12",
    "From": "whatsapp:+15551234567",
    "To": "whatsapp:+15559876543",
    "Body": "Hello, this is a test message",
    "NumMedia": "0",
    "ProfileName": "Test User",
    "WaId": "15551234567"
}

# Message status callback webhook payload
STATUS_CALLBACK_WEBHOOK = {
    "MessageSid": "SMtestmessageid1234567890abcdef12",
    "MessageStatus": "delivered",
    "To": "whatsapp:+15551234567",
    "From": "whatsapp:+15559876543",
    "AccountSid": "ACtestaccountid1234567890abcdef12",
    "MessagingServiceSid": "MGtestserviceid1234567890abcdef12",
    "ErrorCode": None,
    "ErrorMessage": None
}

# Failed message status webhook
FAILED_STATUS_WEBHOOK = {
    "MessageSid": "SMtestmessageid1234567890abcdef12",
    "MessageStatus": "failed",
    "To": "whatsapp:+15551234567",
    "From": "whatsapp:+15559876543",
    "AccountSid": "ACtestaccountid1234567890abcdef12",
    "MessagingServiceSid": "MGtestserviceid1234567890abcdef12",
    "ErrorCode": "63016",
    "ErrorMessage": "The number is not a WhatsApp number"
}

# Bulk user import payload
BULK_USER_IMPORT = {
    "users": [
        {
            "phone_e164": "+15551234001",
            "name": "Test User 1",
            "city": "New York",
            "age": 25,
            "consent_state": "OPT_IN"
        },
        {
            "phone_e164": "+15551234002", 
            "name": "Test User 2",
            "city": "Los Angeles", 
            "age": 30,
            "consent_state": "OPT_IN"
        }
    ]
}

# Campaign creation payload
CAMPAIGN_PAYLOAD = {
    "topic": "Welcome Campaign",
    "template_id": 1,
    "segment_query": {
        "consent_status": "opted_in",
        "attributes.location": "US"
    },
    "rate_limit_per_second": 10,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00"
}