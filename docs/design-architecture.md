# Event Stream Engine - Design & Architecture Documentation

## 1. Executive Summary

The **Event Stream Engine** is a production-grade, event-driven messaging platform designed to deliver personalized WhatsApp messages through Twilio integration. The system handles real-time webhook ingestion, complex campaign orchestration, and maintains auditable logs for compliance and reporting.

## 2. System Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Twilio API    │◄──►│  Event Stream    │◄──►│   PostgreSQL    │
│   (WhatsApp)    │    │     Engine       │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Redis + Celery  │
                       │  (Task Queue)    │
                       └──────────────────┘
```

### 2.2 Core Components

- **Flask Web Application**: REST API and webhook endpoints
- **Celery Workers**: Asynchronous campaign processing
- **PostgreSQL Database**: Persistent data storage with ACID compliance
- **Redis**: Message broker and caching layer
- **Twilio Integration**: WhatsApp API for message delivery

## 3. Strategic Design Decisions

### 3.1 Architecture Pattern: Event-Driven Microservices

**Decision**: Event-driven architecture with clear service boundaries
**Rationale**:
- **Scalability**: Independent scaling of webhook processing vs campaign execution
- **Reliability**: Fault isolation between components
- **Maintainability**: Clear separation of concerns
- **Testability**: Isolated components enable comprehensive testing

### 3.2 Data Storage: PostgreSQL with JSON Columns

**Decision**: PostgreSQL as primary database with JSON attributes
**Rationale**:
- **ACID Compliance**: Critical for financial and compliance data
- **Flexibility**: JSON columns for user attributes and segment definitions
- **Performance**: Excellent indexing and query optimization
- **Audit Trail**: Built-in transaction logging for compliance

### 3.3 Message Queue: Redis + Celery

**Decision**: Redis as broker with Celery for task management
**Rationale**:
- **Performance**: Sub-millisecond latency for real-time processing
- **Reliability**: Persistent task queues with retry mechanisms
- **Scalability**: Horizontal scaling of worker processes
- **Monitoring**: Built-in task monitoring and debugging

### 3.4 API Design: RESTful with Versioning

**Decision**: REST API with `/v1/` prefix and consistent patterns
**Rationale**:
- **Industry Standard**: Familiar patterns for integration
- **Backward Compatibility**: Versioned endpoints support evolution
- **Documentation**: Self-documenting with consistent resource patterns

## 4. Data Model Design

### 4.1 Core Entities

#### Users Table
```sql
users (
  phone_e164 VARCHAR(15) PRIMARY KEY,  -- E.164 format as natural key
  attributes JSONB,                    -- Flexible user data
  consent_status ENUM,                 -- OPT_IN, OPT_OUT
  timezone VARCHAR(50),
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

**Design Rationale**:
- **E.164 as PK**: Natural, immutable identifier for WhatsApp users
- **JSONB Attributes**: Flexible schema for evolving user data requirements
- **Consent Tracking**: GDPR and compliance requirements

#### Messages Table (State Machine)
```sql
messages (
  id UUID PRIMARY KEY,
  campaign_id UUID,
  user_phone VARCHAR(15),
  provider_sid VARCHAR(50),            -- Twilio MessageSid
  status ENUM,                         -- queued → sending → sent → delivered/failed
  error_code VARCHAR(20),              -- Provider error codes for analytics
  rendered_content TEXT,               -- Final message after template rendering
  created_at TIMESTAMP,
  sent_at TIMESTAMP,
  delivered_at TIMESTAMP
)
```

**Design Rationale**:
- **State Machine Pattern**: Clear lifecycle tracking
- **Provider Integration**: Store external IDs for reconciliation
- **Audit Trail**: Complete timeline for compliance and debugging

### 4.2 Campaign Architecture

#### Campaigns Table
```sql
campaigns (
  id UUID PRIMARY KEY,
  name VARCHAR(255),
  template_id UUID,
  segment_definition JSONB,            -- JSON DSL for recipient targeting
  schedule_config JSONB,               -- Scheduling rules and quiet hours
  rate_limit_config JSONB,             -- Rate limiting per campaign
  status ENUM,                         -- draft, scheduled, running, completed, paused
  created_at TIMESTAMP
)
```

**Design Rationale**:
- **JSON DSL**: Flexible segment and scheduling definitions
- **Configuration as Data**: Runtime behavior controlled by data, not code
- **Campaign Lifecycle**: Clear states for operational management

## 5. Integration Architecture

### 5.1 Twilio Webhook Processing

**Pattern**: Store Raw → Normalize → Process
```
Webhook → Raw Storage → Validation → Normalization → Business Logic
```

**Benefits**:
- **Audit Compliance**: Complete webhook history
- **Data Quality**: Validation and error tracking
- **Debugging**: Original payloads available for troubleshooting

### 5.2 Campaign Orchestration Flow

```
Trigger Event → Segment Evaluation → Template Rendering → 
Consent Check → Rate Limiting → Queue for Delivery → 
Send via Twilio → Status Tracking → Retry Logic
```

**Design Principles**:
- **Idempotency**: Safe retry of failed operations
- **Observability**: Each step logged for monitoring
- **Graceful Degradation**: System continues operating during partial failures

## 6. Scalability & Performance

### 6.1 Horizontal Scaling Strategy

- **Web Tier**: Stateless Flask applications behind load balancer
- **Worker Tier**: Multiple Celery workers with auto-scaling
- **Database Tier**: Read replicas for analytics queries
- **Cache Tier**: Redis clustering for high availability

### 6.2 Performance Optimizations

- **Database Indexing**: Composite indexes on query patterns
- **Connection Pooling**: Optimized database connection management
- **Async Processing**: Non-blocking webhook responses
- **Caching Strategy**: Redis for frequently accessed data

## 7. Security & Compliance

### 7.1 Data Protection

- **Encryption at Rest**: Database encryption for PII
- **Encryption in Transit**: TLS for all API communications
- **Access Control**: Role-based permissions for API endpoints
- **Audit Logging**: Complete activity trail for compliance

### 7.2 Privacy Compliance

- **Consent Management**: Explicit opt-in/opt-out tracking
- **Data Retention**: Configurable retention policies
- **Right to Deletion**: User data purging capabilities
- **Anonymization**: PII removal for analytics

## 8. Operational Excellence

### 8.1 Monitoring Strategy

- **Application Metrics**: Response times, error rates, throughput
- **Business Metrics**: Delivery rates, conversion tracking, user engagement
- **Infrastructure Metrics**: Database performance, queue depth, worker utilization
- **Alerting**: Proactive notification of issues

### 8.2 Deployment Strategy

- **Containerization**: Docker for consistent environments
- **Infrastructure as Code**: Docker Compose for local development
- **Database Migrations**: Versioned schema changes
- **Zero-Downtime Deployment**: Blue-green deployment patterns

## 9. Testing Strategy

### 9.1 Test Pyramid

- **Unit Tests**: Business logic validation (70%)
- **Integration Tests**: Component interaction validation (20%)
- **End-to-End Tests**: Full workflow validation (10%)

### 9.2 Test Coverage Areas

- **Data Validation**: Phone number formats, segment rules
- **Template Rendering**: Variable substitution, error handling
- **Webhook Processing**: Twilio integration, error scenarios
- **Campaign Orchestration**: Complete message lifecycle

## 10. Technical Debt Management

### 10.1 Code Quality Standards

- **Type Hints**: Python type annotations for maintainability
- **Code Formatting**: Black + flake8 for consistent style
- **Documentation**: Comprehensive docstrings and API documentation
- **Review Process**: Code reviews for all changes

### 10.2 Evolution Strategy

- **API Versioning**: Backward compatibility for integrations
- **Database Migrations**: Safe, reversible schema changes
- **Feature Flags**: Gradual rollout of new functionality
- **Performance Monitoring**: Continuous optimization based on metrics

---

**Document Version**: 1.0  
**Last Updated**: October 4, 2025  
**Authors**: Event Stream Engine Development Team