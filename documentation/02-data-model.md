# Data Model & Entity Relationships

## 📊 Complete Data Model Overview

The Event Stream Engine data model is designed around **event-driven messaging workflows** with strict compliance and audit requirements. The schema supports real-time webhook processing, campaign orchestration, and comprehensive tracking.

## 🏗️ Entity Relationship Diagram

```
                    ┌─────────────────────────────────────┐
                    │              CORE ENTITIES          │
                    └─────────────────────────────────────┘
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            │                            │                            │
    ┌─────────────┐                ┌─────────────┐              ┌─────────────┐
    │    User     │                │  Campaign   │              │  Template   │
    │             │                │             │              │             │
    │ phone_e164* │────────────────│ template_id │─────────────▶│ id*         │
    │ attributes  │                │ segment_id  │              │ name        │
    │ consent     │                │ status      │              │ content     │
    └─────────────┘                └─────────────┘              └─────────────┘
            │                            │                            │
            │                            │                            │
            │                    ┌─────────────┐                     │
            │                    │  Segment    │                     │
            │                    │             │                     │
            │                    │ id*         │◀────────────────────┘
            │                    │ name        │
            │                    │ filter_json │
            │                    └─────────────┘
            │                            │
            └────────────────────────────┼────────────────────────────┐
                                         │                            │
                    ┌─────────────────────────────────────┐           │
                    │           EXECUTION ENTITIES        │           │
                    └─────────────────────────────────────┘           │
                                         │                            │
            ┌────────────────────────────┼────────────────────────────┘
            │                            │                            
    ┌─────────────┐                ┌─────────────┐              ┌─────────────┐
    │   Message   │                │ Delivery    │              │  Inbound    │
    │             │                │  Receipt    │              │   Event     │
    │ id*         │────────────────│ message_sid │              │ id*         │
    │ recipient   │                │ status      │              │ from_phone  │
    │ campaign_id │                │ error_code  │              │ raw_payload │
    │ status      │                │ raw_payload │              │ body        │
    │ provider_sid│◀───────────────│             │              └─────────────┘
    └─────────────┘                └─────────────┘                     
```

## 📋 Entity Specifications

### **1. User Entity - Primary Customer Record**

**Purpose**: Central repository for all customer/recipient data with E.164 phone number as primary key.

```sql
CREATE TABLE users (
    phone_e164 VARCHAR(20) PRIMARY KEY,  -- Internationally formatted phone
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    consent_state VARCHAR(20) DEFAULT 'OPT_IN',
    consent_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    attributes JSONB DEFAULT '{}',  -- Flexible customer data
    last_message_received TIMESTAMP
);
```

**Key Design Decisions**:
- **E.164 Format**: `+1234567890` ensures global phone number compatibility
- **JSONB Attributes**: Flexible schema for customer data (`{"name": "John", "city": "NYC", "tier": "premium"}`)
- **Consent Tracking**: Explicit consent state with timestamp for compliance
- **GIN Index**: Efficient querying on JSON attributes for segmentation

**Sample Data**:
```json
{
  "phone_e164": "+14155551234",
  "consent_state": "OPT_IN", 
  "attributes": {
    "name": "John Doe",
    "city": "San Francisco", 
    "signup_date": "2024-01-15",
    "tier": "premium"
  }
}
```

### **2. Campaign Entity - Marketing Orchestration**

**Purpose**: Defines marketing campaigns with targeting, scheduling, and execution tracking.

```sql
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    template_id UUID REFERENCES templates(id),
    segment_id UUID REFERENCES segments(id),
    status VARCHAR(20) DEFAULT 'DRAFT',
    schedule_time TIMESTAMP,  -- NULL = immediate
    rate_limit_per_second INTEGER DEFAULT 1,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00'
);
```

**Status State Machine**:
```
DRAFT → READY → RUNNING → COMPLETED
   ↓       ↓       ↓
PAUSED ← PAUSED ← PAUSED
```

**Key Features**:
- **Template Integration**: Links to reusable message templates
- **Segment Targeting**: JSON-based audience filtering
- **Rate Limiting**: Configurable per-campaign throttling
- **Quiet Hours**: Timezone-aware delivery scheduling
- **Execution Tracking**: Real-time message counts and status

### **3. Template Entity - Content Management**

**Purpose**: Reusable message templates with variable substitution support.

```sql
CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    content TEXT NOT NULL,  -- "Hello {name}, your {product} order is ready!"
    variables JSONB DEFAULT '[]',  -- ["name", "product", "location"]
    character_count INTEGER GENERATED ALWAYS AS (char_length(content)) STORED
);
```

**Template Processing Example**:
```
Template: "Hello {name}, your order from {city} is ready for pickup!"
Variables: ["name", "city"]
User Data: {"name": "Sarah", "city": "Austin"}
Rendered: "Hello Sarah, your order from Austin is ready for pickup!"
```

### **4. Segment Entity - Audience Targeting**

**Purpose**: JSON DSL-based user filtering for campaign targeting.

```sql
CREATE TABLE segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    filter_criteria JSONB NOT NULL,
    estimated_audience_size INTEGER DEFAULT 0
);
```

**Filter DSL Examples**:
```json
// Simple attribute filter
{
  "attribute": "city",
  "operator": "equals", 
  "value": "San Francisco"
}

// Complex compound filter
{
  "operator": "AND",
  "conditions": [
    {"attribute": "tier", "operator": "equals", "value": "premium"},
    {"attribute": "signup_date", "operator": "after", "value": "2024-01-01"}
  ]
}
```

### **5. Message Entity - Delivery Tracking**

**Purpose**: Individual message records with complete delivery lifecycle tracking.

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_phone VARCHAR(20) NOT NULL REFERENCES users(phone_e164),
    campaign_id UUID REFERENCES campaigns(id),
    rendered_content TEXT NOT NULL,
    provider_sid VARCHAR(50),  -- Twilio MessageSid
    status VARCHAR(20) DEFAULT 'QUEUED',
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    error_code INTEGER,
    retry_count INTEGER DEFAULT 0
);
```

**Message State Machine**:
```
QUEUED → SENDING → SENT → DELIVERED ✓
   ↓        ↓       ↓         ↓
FAILED ← FAILED ← FAILED ← UNDELIVERED
```

**Retry Logic**:
- **Exponential Backoff**: 1min, 5min, 15min, 1hr intervals
- **Max Retries**: 3 attempts before permanent failure
- **Error Codes**: Twilio-specific error classification

### **6. Delivery Receipt Entity - Webhook Tracking**

**Purpose**: Immutable audit trail of all Twilio delivery status callbacks.

```sql
CREATE TABLE delivery_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_sid VARCHAR(50) NOT NULL,
    raw_payload JSONB NOT NULL,  -- Complete webhook data
    message_status VARCHAR(20),   -- delivered, failed, etc.
    error_code INTEGER,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Webhook Processing Flow**:
1. **Raw Persistence**: Immediate storage of complete webhook payload
2. **Normalization**: Extract structured fields (status, error_code, timestamps)
3. **Message Update**: Update corresponding message record status
4. **Audit Trail**: Maintain immutable delivery history

### **7. Inbound Event Entity - Customer Messages**

**Purpose**: Complete record of inbound WhatsApp messages from customers.

```sql
CREATE TABLE inbound_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_payload JSONB NOT NULL,
    message_sid VARCHAR(50),
    from_phone VARCHAR(20),
    body TEXT,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(20) DEFAULT 'PENDING'
);
```

**Processing Pipeline**:
1. **Webhook Reception**: Store raw Twilio payload
2. **Phone Normalization**: Extract and validate E.164 format
3. **Auto-Reply Logic**: Trigger automated responses if configured
4. **Consent Processing**: Handle STOP/START commands
5. **Analytics Update**: Update customer interaction metrics

## 🔍 Query Patterns & Indexes

### **High-Performance Indexes**

```sql
-- User segmentation queries
CREATE INDEX idx_users_attributes_gin ON users USING gin(attributes);
CREATE INDEX idx_users_consent_state ON users(consent_state);

-- Campaign execution queries  
CREATE INDEX idx_messages_recipient ON messages(recipient_phone);
CREATE INDEX idx_messages_campaign ON messages(campaign_id);
CREATE INDEX idx_messages_status_created ON messages(status, created_at);

-- Reporting and analytics queries
CREATE INDEX idx_delivery_receipts_status_received ON delivery_receipts(message_status, received_at);
CREATE INDEX idx_inbound_events_from_received ON inbound_events(from_phone, received_at);

-- Webhook lookup optimization
CREATE INDEX idx_messages_provider_sid ON messages(provider_sid);
CREATE INDEX idx_delivery_receipts_message_sid ON delivery_receipts(message_sid);
```

### **Common Query Patterns**

**1. Segment Evaluation**
```sql
-- Find users matching segment criteria
SELECT phone_e164, attributes 
FROM users 
WHERE consent_state = 'OPT_IN'
  AND attributes @> '{"city": "San Francisco", "tier": "premium"}';
```

**2. Campaign Performance**
```sql
-- Campaign delivery metrics
SELECT 
  c.name,
  COUNT(m.id) as total_sent,
  COUNT(CASE WHEN dr.message_status = 'delivered' THEN 1 END) as delivered,
  AVG(EXTRACT(EPOCH FROM (dr.received_at - m.sent_at))/60) as avg_delivery_time_mins
FROM campaigns c
JOIN messages m ON c.id = m.campaign_id
LEFT JOIN delivery_receipts dr ON m.provider_sid = dr.message_sid
WHERE c.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY c.id, c.name;
```

**3. Real-time Dashboard**
```sql
-- System health metrics
SELECT 
  (SELECT COUNT(*) FROM campaigns WHERE status IN ('READY', 'RUNNING')) as active_campaigns,
  (SELECT COUNT(*) FROM users WHERE consent_state = 'OPT_IN') as opted_in_users,
  (SELECT COUNT(*) FROM messages WHERE created_at >= CURRENT_DATE AND status = 'DELIVERED') as delivered_today,
  (SELECT COUNT(*) FROM inbound_events WHERE received_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour') as recent_inbound;
```

## 🛡️ Data Integrity & Constraints

### **Referential Integrity**
- **CASCADE DELETE**: Campaign deletion removes associated messages
- **RESTRICT DELETE**: Template/Segment deletion blocked if referenced by active campaigns
- **FOREIGN KEY**: All relationships enforced at database level

### **Data Validation**
- **Phone Format**: E.164 regex validation (`^\\+[1-9]\\d{1,14}$`)
- **Enum Constraints**: Status fields restricted to valid state machine values
- **JSON Schema**: Template variables and segment criteria validated
- **Timestamp Logic**: Delivery times must be after send times

### **Backup & Recovery**
- **Point-in-Time Recovery**: PostgreSQL WAL-based backup strategy
- **Cross-Region Replication**: Google Cloud SQL high availability setup
- **Audit Trail Retention**: 7-year retention for compliance requirements

---

*This data model provides a robust foundation for enterprise-scale messaging operations with comprehensive audit trails, performance optimization, and regulatory compliance.*