# Event Stream Engine - System Architecture & Design

## 🎯 Executive Summary

The Event Stream Engine is a **production-grade, event-driven messaging platform** designed for personalized WhatsApp delivery at scale via Twilio. This document outlines the complete system architecture, data contracts (DDL), and technical implementation decisions for a robust, scalable, and compliant messaging infrastructure.

## 🏗️ System Architecture Overview

### **High-Level Architecture Pattern: Event-Driven Microservices**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Twilio API    │────│  Event Stream    │────│  PostgreSQL     │
│   (WhatsApp)    │    │    Engine        │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────│  Redis Broker   │──────────────┘
                        │  (Celery)       │
                        └─────────────────┘
```

### **Core Technology Stack**

| **Layer** | **Technology** | **Purpose** |
|-----------|----------------|-------------|
| **Web Framework** | Flask 3.1.2 | RESTful API, webhook endpoints, web UI |
| **Database** | PostgreSQL (Cloud SQL) | ACID-compliant data persistence |
| **ORM** | SQLAlchemy 2.0.43 | Database abstraction, migrations |
| **Message Broker** | Redis | Async task queuing, caching, rate limiting |
| **Task Queue** | Celery | Background campaign processing |
| **Validation** | Pydantic 2.11.10 | API request/response validation |
| **External API** | Twilio SDK 9.8.3 | WhatsApp message delivery |
| **Containerization** | Docker + Docker Compose | Development and deployment |
| **Cloud Platform** | Google Cloud Platform | Production hosting (Cloud Run, Cloud SQL) |

---

## 📊 Data Model & Contracts (DDL)

### **Core Entity Relationship Diagram**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │────▶│   Message   │────▶│ Delivery    │
│             │     │             │     │  Receipt    │
│ phone_e164* │     │ campaign_id │     │ message_sid │
│ attributes  │     │ status      │     │ status      │
│ consent     │     │ provider_sid│     │ error_code  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │
       │            ┌─────────────┐              │
       └───────────▶│  Campaign   │◀─────────────┘
                    │             │
                    │ topic       │
                    │ template_id │
                    │ status      │
                    └─────────────┘
                           │
                    ┌─────────────┐
                    │  Template   │
                    │             │
                    │ name        │
                    │ content     │
                    │ channel     │
                    └─────────────┘
                           
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│Subscription │     │  Segment    │     │  Inbound    │
│             │     │             │     │  Event      │
│ user_phone  │     │ name        │     │ from_phone  │
│ topic       │     │definition   │     │ raw_payload │
└─────────────┘     └─────────────┘     └─────────────┘
```

### **Complete DDL Schema**

#### **1. Users Table - Primary Entity**
```sql
CREATE TABLE users (
    phone_e164 VARCHAR(16) PRIMARY KEY,  -- E.164 format: +1234567890
    attributes JSONB DEFAULT '{}',  -- Flexible user data: {"name": "John", "city": "NYC"}
    consent_state VARCHAR(20) DEFAULT 'OPT_IN',  -- OPT_IN, OPT_OUT, STOP
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_phone_format CHECK (phone_e164 ~ '^\\+[1-9]\\d{1,14}$'),
    CONSTRAINT valid_consent_state CHECK (consent_state IN ('OPT_IN', 'OPT_OUT', 'STOP'))
);

-- Performance indexes
CREATE INDEX idx_users_consent_state ON users(consent_state);
CREATE INDEX idx_users_attributes_gin ON users USING gin(attributes);
```

#### **3. Subscriptions Table - User Topic Relations**
```sql
CREATE TABLE subscriptions (
    user_phone VARCHAR(16) NOT NULL REFERENCES users(phone_e164),
    topic VARCHAR(100) NOT NULL,
    
    PRIMARY KEY (user_phone, topic)
);
```

#### **3. Campaigns Table - Marketing Entity**
```sql
CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(100) NOT NULL,  -- Campaign topic (e.g., 'price_alert')
    template_id INTEGER NOT NULL REFERENCES templates(id),
    
    schedule_time TIMESTAMP,  -- NULL = immediate, future = scheduled
    status VARCHAR(50) DEFAULT 'DRAFT',  -- DRAFT, READY, RUNNING, COMPLETED
    
    -- Rate limiting configuration
    rate_limit_per_second INTEGER DEFAULT 10,
    quiet_hours_start VARCHAR(5),  -- Time format: '22:00'
    quiet_hours_end VARCHAR(5),    -- Time format: '08:00'
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_schedule_time ON campaigns(schedule_time);
```

#### **4. Templates Table - Content Entity**
```sql
CREATE TABLE templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    channel VARCHAR(20) DEFAULT 'whatsapp',
    locale VARCHAR(10) DEFAULT 'en_US',
    content TEXT NOT NULL,  -- "Hello {name}, your order from {city} is ready!"
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_templates_name ON templates(name);
```

#### **5. Segments Table - Targeting Entity**
```sql
CREATE TABLE segments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    
    -- JSON DSL for user filtering
    definition_json JSONB,  -- {"attribute": "city", "value": "Colombo"}
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_segments_name ON segments(name);
CREATE INDEX idx_segments_definition_json ON segments USING gin(definition_json);
```

#### **6. Messages Table - Delivery Entity**
```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    recipient_phone VARCHAR(16) NOT NULL REFERENCES users(phone_e164),
    
    -- State machine tracking
    status VARCHAR(20) DEFAULT 'QUEUED',  -- QUEUED → SENDING → SENT → DELIVERED/FAILED
    provider_sid VARCHAR(50) UNIQUE,  -- Twilio MessageSid
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    
    -- Error handling
    error_code INTEGER,
    
    CONSTRAINT valid_message_status CHECK (status IN ('QUEUED', 'SENDING', 'SENT', 'DELIVERED', 'READ', 'FAILED', 'UNDELIVERED'))
);

-- Critical performance indexes
CREATE INDEX idx_messages_recipient_phone ON messages(recipient_phone);
CREATE INDEX idx_messages_campaign_id ON messages(campaign_id);
CREATE INDEX idx_messages_status_created ON messages(status, created_at);
CREATE INDEX idx_messages_provider_sid ON messages(provider_sid);
```

#### **7. Delivery Receipts Table - Tracking Entity**
```sql
CREATE TABLE delivery_receipts (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    raw_payload JSONB NOT NULL,  -- Complete webhook payload for audit
    
    -- Normalized fields
    message_sid VARCHAR(50),  -- Links to messages.provider_sid
    message_status VARCHAR(20),  -- delivered, failed, undelivered, etc.
    error_code INTEGER,
    
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key relationships
    message_id TEXT REFERENCES messages(id),
    user_phone VARCHAR(16) REFERENCES users(phone_e164)
);

CREATE INDEX idx_delivery_receipts_message_sid ON delivery_receipts(message_sid);
CREATE INDEX idx_delivery_receipts_status ON delivery_receipts(message_status);
CREATE INDEX idx_delivery_receipts_received_at ON delivery_receipts(received_at);
```

#### **8. Inbound Events Table - Webhook Entity**
```sql
CREATE TABLE events_inbound (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    raw_payload JSONB NOT NULL,  -- Complete inbound message payload
    
    -- Normalized fields
    message_sid VARCHAR(50),
    from_phone VARCHAR(16),
    channel_type VARCHAR(20),
    normalized_body TEXT,
    
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key relationships
    message_id TEXT REFERENCES messages(id),
    user_phone VARCHAR(16) REFERENCES users(phone_e164)
);

CREATE INDEX idx_inbound_events_from_phone ON events_inbound(from_phone);
CREATE INDEX idx_inbound_events_channel_type ON events_inbound(channel_type);
CREATE INDEX idx_inbound_events_message_sid ON events_inbound(message_sid);
```

---

## 🔧 Architectural Design Patterns

### **1. Event-Driven Architecture**
- **Webhook Ingestion**: Immediate persistence of raw payloads
- **Async Processing**: Celery tasks for complex business logic
- **State Machines**: Clear message lifecycle tracking
- **Audit Trail**: Complete event history for compliance

### **2. Data Integrity Patterns**
- **E.164 Phone Validation**: Enforced at database and application levels
- **JSON Schema Validation**: Pydantic models for API contracts
- **Foreign Key Constraints**: Referential integrity across entities
- **Optimistic Locking**: Timestamp-based conflict resolution

### **3. Performance Optimization**
- **Strategic Indexing**: Query-specific database indexes
- **Connection Pooling**: SQLAlchemy connection management
- **Redis Caching**: Frequent query result caching
- **Batch Processing**: Bulk operations for campaign execution

### **4. Compliance & Security**
- **Consent Tracking**: Explicit opt-in/opt-out state management
- **Quiet Hours**: Timezone-aware delivery scheduling
- **Rate Limiting**: Redis-backed throttling mechanisms
- **Audit Logging**: Immutable event trail for compliance

---

## 🚀 Deployment Architecture

### **Production Environment (Google Cloud)**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Cloud Run     │────│   Cloud SQL      │────│  Redis Cloud    │
│   (Flask App)   │    │  (PostgreSQL)    │    │   (Managed)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────│  Cloud Logging  │──────────────┘
                        │  & Monitoring   │
                        └─────────────────┘
```

### **Scalability Considerations**
- **Horizontal Scaling**: Cloud Run auto-scaling based on request volume
- **Database Scaling**: Cloud SQL read replicas for reporting queries
- **Task Queue Scaling**: Multiple Celery workers with auto-scaling groups
- **Caching Layer**: Redis cluster for high-availability caching

---

*This architecture provides a robust foundation for a production-grade messaging platform with enterprise-level scalability, compliance, and maintainability.*