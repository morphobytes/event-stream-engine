# API Reference Documentation

## 🎯 Overview

Complete REST API documentation for the Event Stream Engine with request/response examples, authentication details, and error handling specifications.

**Base URL**: `https://your-domain.com/api/v1`  
**Authentication**: API Key (future enhancement)  
**Content Type**: `application/json`

---

## 📱 User Management APIs

### **List Users**
```http
GET /api/v1/users
```

**Query Parameters**:
- `page` (optional): Page number for pagination (default: 1)
- `per_page` (optional): Items per page (default: 20, max: 100)
- `consent_state` (optional): Filter by consent state (`OPT_IN`, `OPT_OUT`, `STOP`)

**Response Example**:
```json
{
  "users": [
    {
      "phone_e164": "+14155551234",
      "created_at": "2024-01-15T10:30:00Z",
      "consent_state": "OPT_IN",
      "consent_updated_at": "2024-01-15T10:30:00Z",
      "attributes": {
        "name": "John Doe",
        "city": "San Francisco",
        "tier": "premium"
      },
      "last_message_received": "2024-01-20T14:22:00Z"
    }
  ],
  "total": 1500,
  "page": 1,
  "per_page": 20,
  "pages": 75
}
```

### **Create User**
```http
POST /api/v1/users
```

**Request Body**:
```json
{
  "phone_e164": "+14155551234",
  "consent_state": "OPT_IN",
  "attributes": {
    "name": "Jane Smith",
    "city": "Austin",
    "signup_source": "website"
  }
}
```

**Response** (201 Created):
```json
{
  "phone_e164": "+14155551234",
  "created_at": "2024-01-25T16:45:00Z",
  "consent_state": "OPT_IN",
  "message": "User created successfully"
}
```

### **Get User Details**
```http
GET /api/v1/users/{phone_e164}
```

**Path Parameters**:
- `phone_e164`: E.164 formatted phone number (e.g., `+14155551234`)

### **Update User**
```http
PUT /api/v1/users/{phone_e164}
```

**Request Body**:
```json
{
  "consent_state": "OPT_OUT",
  "attributes": {
    "name": "Jane Smith Updated",
    "tier": "enterprise",
    "last_login": "2024-01-25"
  }
}
```

### **Delete User**
```http
DELETE /api/v1/users/{phone_e164}
```

**Response** (200 OK):
```json
{
  "message": "User deleted successfully",
  "phone_e164": "+14155551234"
}
```

### **Bulk User Upload**
```http
POST /api/v1/users/bulk/upload
```

**Request**: Multipart form data with CSV or JSON file

**CSV Format Example**:
```csv
phone_e164,name,city,tier,consent_state
+14155551234,John Doe,San Francisco,premium,OPT_IN
+14155555678,Jane Smith,Austin,standard,OPT_IN
```

**Response**:
```json
{
  "message": "Bulk upload completed",
  "processed": 1000,
  "created": 850,
  "updated": 150,
  "errors": 0,
  "validation_errors": []
}
```

---

## 📊 Campaign Management APIs

### **List Campaigns**
```http
GET /api/v1/campaigns
```

**Query Parameters**:
- `status` (optional): Filter by campaign status
- `page`, `per_page`: Pagination parameters

**Response Example**:
```json
{
  "campaigns": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Welcome Campaign",
      "description": "New user onboarding messages",
      "status": "RUNNING",
      "created_at": "2024-01-15T10:00:00Z",
      "schedule_time": null,
      "template": {
        "id": "template-uuid",
        "name": "Welcome Template",
        "content": "Welcome {name}! Thanks for joining us."
      },
      "segment": {
        "id": "segment-uuid", 
        "name": "New Users"
      },
      "messages_sent": 245,
      "messages_failed": 3,
      "rate_limit_per_second": 2
    }
  ],
  "total": 15
}
```

### **Create Campaign**
```http
POST /api/v1/campaigns
```

**Request Body**:
```json
{
  "name": "Spring Promotion",
  "description": "Spring sale announcement campaign",
  "template_id": "template-uuid-here",
  "segment_id": "segment-uuid-here",
  "schedule_time": "2024-03-15T09:00:00Z",
  "rate_limit_per_second": 3,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "08:00"
}
```

### **Trigger Campaign**
```http
POST /api/v1/campaigns/{campaign_id}/trigger
```

**Response**:
```json
{
  "message": "Campaign triggered successfully",
  "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
  "estimated_recipients": 1250,
  "execution_started": true
}
```

### **Get Campaign Performance**
```http
GET /api/v1/reporting/campaigns/{campaign_id}/summary
```

**Response**:
```json
{
  "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
  "campaign_name": "Welcome Campaign",
  "performance_metrics": {
    "messages_sent": 1000,
    "messages_delivered": 950,
    "messages_failed": 50,
    "delivery_rate": 95.0,
    "average_delivery_time_minutes": 2.3
  },
  "status_breakdown": {
    "DELIVERED": 950,
    "FAILED": 30,
    "UNDELIVERED": 15,
    "SENT": 5
  },
  "error_analysis": {
    "invalid_phone_number": 25,
    "network_error": 20,
    "rate_limit_exceeded": 5
  },
  "execution_timeline": {
    "started_at": "2024-01-25T09:00:00Z",
    "completed_at": "2024-01-25T09:45:00Z",
    "duration_minutes": 45
  }
}
```

---

## 📝 Template Management APIs

### **List Templates**
```http
GET /api/v1/templates
```

**Response Example**:
```json
{
  "templates": [
    {
      "id": "template-uuid",
      "name": "Welcome Template",
      "content": "Hi {name}! Welcome to {company}. Your account in {city} is ready!",
      "variables": ["name", "company", "city"],
      "character_count": 65,
      "created_at": "2024-01-10T14:30:00Z",
      "is_active": true
    }
  ]
}
```

### **Create Template**
```http
POST /api/v1/templates
```

**Request Body**:
```json
{
  "name": "Order Confirmation",
  "content": "Hi {customer_name}! Your order #{order_id} for ${total_amount} has been confirmed. Delivery to {address} expected by {delivery_date}.",
  "variables": ["customer_name", "order_id", "total_amount", "address", "delivery_date"]
}
```

---

## 🎯 Segment Management APIs

### **List Segments**
```http
GET /api/v1/segments
```

**Response Example**:
```json
{
  "segments": [
    {
      "id": "segment-uuid",
      "name": "Premium SF Users",
      "description": "Premium tier users in San Francisco",
      "filter_criteria": {
        "operator": "AND",
        "conditions": [
          {"attribute": "city", "operator": "equals", "value": "San Francisco"},
          {"attribute": "tier", "operator": "equals", "value": "premium"}
        ]
      },
      "estimated_audience_size": 1250,
      "created_at": "2024-01-12T11:15:00Z"
    }
  ]
}
```

### **Create Segment**
```http
POST /api/v1/segments
```

**Request Body**:
```json
{
  "name": "Recent Signups",
  "description": "Users who signed up in the last 30 days",
  "filter_criteria": {
    "attribute": "signup_date",
    "operator": "after",
    "value": "2024-01-01"
  }
}
```

### **Evaluate Segment**
```http
POST /api/v1/segments/{segment_id}/evaluate
```

**Response**:
```json
{
  "segment_id": "segment-uuid",
  "matching_users": 1250,
  "sample_users": [
    "+14155551234",
    "+14155555678",
    "+14155559999"
  ],
  "evaluation_time_ms": 150
}
```

---

## 📈 Reporting & Analytics APIs

### **Message Status Tracking**
```http
GET /api/v1/reporting/messages/status
```

**Query Parameters**:
- `campaign_id` (optional): Filter by specific campaign
- `start_date`, `end_date`: Date range filter
- `status`: Filter by message status

**Response Example**:
```json
{
  "messages": [
    {
      "id": "message-uuid",
      "recipient_phone": "+14155551234",
      "campaign_name": "Welcome Campaign",
      "status": "DELIVERED",
      "sent_at": "2024-01-25T10:15:00Z",
      "delivered_at": "2024-01-25T10:17:00Z",
      "delivery_time_seconds": 120,
      "error_code": null
    }
  ],
  "summary": {
    "total_messages": 5000,
    "delivered": 4750,
    "failed": 200,
    "pending": 50,
    "delivery_rate": 95.0
  }
}
```

### **System Dashboard Metrics**
```http
GET /api/v1/monitoring/dashboard
```

**Response Example**:
```json
{
  "system_health": {
    "active_campaigns": 5,
    "total_users": 15000,
    "opted_in_users": 14250,
    "opted_out_users": 750
  },
  "activity_24h": {
    "messages_sent": 2500,
    "messages_delivered": 2375,
    "inbound_messages": 150,
    "delivery_rate": 95.0
  },
  "performance_metrics": {
    "average_delivery_time_minutes": 2.1,
    "system_uptime_hours": 720,
    "error_rate_percent": 2.0
  },
  "recent_errors": [
    {
      "timestamp": "2024-01-25T14:30:00Z",
      "error_code": 21211,
      "message": "Invalid 'To' phone number",
      "count": 5
    }
  ]
}
```

### **Inbound Activity Monitoring**
```http
GET /api/v1/monitoring/inbound
```

**Query Parameters**:
- `hours` (optional): Hours to look back (default: 24)
- `limit` (optional): Maximum events to return (default: 100)

**Response Example**:
```json
{
  "inbound_events": [
    {
      "id": "event-uuid",
      "from_phone": "+14155551234",
      "to_phone": "+15551234567",
      "body": "Hello, I need help with my order",
      "received_at": "2024-01-25T15:30:00Z",
      "message_sid": "SM1234567890abcdef"
    }
  ],
  "summary": {
    "total_inbound_24h": 150,
    "unique_senders": 125,
    "average_per_hour": 6.25,
    "stop_commands": 3
  }
}
```

---

## 🔗 Webhook Endpoints

### **Inbound Message Webhook**
```http
POST /webhooks/inbound
```

**Twilio Request Body** (application/x-www-form-urlencoded):
```
MessageSid=SM1234567890abcdef
From=whatsapp:+14155551234
To=whatsapp:+15551234567
Body=Hello, I need support
NumMedia=0
```

**Response** (200 OK):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response></Response>
```

### **Delivery Status Webhook**
```http
POST /webhooks/status
```

**Twilio Request Body**:
```
MessageSid=SM1234567890abcdef
MessageStatus=delivered
To=+14155551234
From=+15551234567
ErrorCode=
```

**Response** (200 OK):
```json
{
  "status": "received"
}
```

---

## ⚠️ Error Handling

### **Standard Error Response Format**
```json
{
  "error": "validation_error",
  "message": "Invalid phone number format",
  "details": {
    "field": "phone_e164",
    "provided": "1234567890",
    "expected": "E.164 format (+1234567890)"
  },
  "timestamp": "2024-01-25T16:45:00Z",
  "request_id": "req_abc123"
}
```

### **HTTP Status Codes**
- `200` - Success
- `201` - Created successfully 
- `400` - Bad Request (validation error)
- `401` - Unauthorized (authentication required)
- `404` - Resource not found
- `409` - Conflict (duplicate resource)
- `422` - Unprocessable Entity (business logic error)
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error

### **Common Error Types**

#### **Validation Errors (400)**
```json
{
  "error": "validation_error",
  "message": "Phone number must be in E.164 format",
  "field": "phone_e164"
}
```

#### **Resource Not Found (404)**
```json
{
  "error": "not_found",
  "message": "User with phone +14155551234 not found"
}
```

#### **Rate Limiting (429)**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after_seconds": 60
}
```

---

## 🔐 Authentication & Security

### **API Key Authentication** (Future Enhancement)
```http
Authorization: Bearer your_api_key_here
```

### **Webhook Security**
Twilio webhooks include signature verification:
```python
# Verify Twilio webhook signature
from twilio.request_validator import RequestValidator

validator = RequestValidator(auth_token)
if validator.validate(request.url, request.form, request.headers.get('X-Twilio-Signature')):
    # Process webhook
    pass
```

### **Rate Limiting**
- **Global Limit**: 1000 requests per hour per IP
- **Authenticated Limit**: 10,000 requests per hour per API key
- **Webhook Endpoints**: No rate limiting (Twilio callbacks)

---

## 📊 API Usage Examples

### **Complete Campaign Workflow**
```bash
# 1. Create template
curl -X POST http://localhost:5000/api/v1/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Welcome Message",
    "content": "Hi {name}! Welcome to our service.",
    "variables": ["name"]
  }'

# 2. Create segment
curl -X POST http://localhost:5000/api/v1/segments \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Users",
    "filter_criteria": {
      "attribute": "signup_date",
      "operator": "after", 
      "value": "2024-01-01"
    }
  }'

# 3. Create campaign
curl -X POST http://localhost:5000/api/v1/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Welcome Campaign",
    "template_id": "template-uuid",
    "segment_id": "segment-uuid"
  }'

# 4. Trigger campaign
curl -X POST http://localhost:5000/api/v1/campaigns/campaign-uuid/trigger

# 5. Monitor performance
curl http://localhost:5000/api/v1/reporting/campaigns/campaign-uuid/summary
```

---

*This comprehensive API reference provides complete documentation for integrating with and operating the Event Stream Engine messaging platform.*
