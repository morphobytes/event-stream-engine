# Event Stream Engine - AI Coding Agent Instructions

## Project Overview
This is a production-grade event-driven messaging platform for personalized WhatsApp delivery via Twilio. The system handles real-time webhook ingestion, complex campaign orchestration, and maintains auditable logs for compliance.

**Core Stack:** Flask + SQLAlchemy, PostgreSQL (Cloud SQL), Redis (broker/cache), Celery (async processing), Docker/GCP

## Architecture Components

### 1. Core Application Structure (`app/`)
- **`api/`** - Flask routes for Twilio webhooks (inbound messages, status callbacks) and versioned REST API
- **`core/`** - SQLAlchemy models defining the data contracts (Users, Campaigns, Messages, Events, etc.)
- **`runner/`** - Celery workers for campaign orchestration (segment evaluation, template rendering, rate limiting)
- **`ingestion/`** - Bulk data processing (CSV/JSON user imports with E.164 validation and deduplication)
- **`main.py`** - Application factory initializing Flask, Celery, and database connections

### 2. Data Model Patterns
- **Primary Keys:** Use E.164 phone numbers as PK for Users table (phone_number field)
- **State Machines:** Messages table tracks delivery lifecycle (queued → sending → sent → delivered/failed)
- **Audit Trail:** Store both raw webhook data and normalized records for compliance
- **JSON Attributes:** Use PostgreSQL JSON columns for flexible user attributes and segment definitions

### 3. Key Integration Points
- **Twilio Webhooks:** Handle inbound messages (`/webhooks/inbound`) and status callbacks (`/webhooks/status`)
- **Campaign Runner:** Background Celery tasks that evaluate segments → render templates → enforce consent/rate limits → send via Twilio API
- **Bulk Ingestion:** Accept CSV/JSON files, validate E.164 format, dedupe, and merge user attributes

## Development Workflows

### Environment Setup
```bash
source .venv/bin/activate  # Activate virtual environment
pip install -r requirements.txt
```

### Local Development Stack
```bash
docker-compose up -d  # Starts PostgreSQL, Redis, and Celery worker
flask run  # Start development server
```

### Database Migrations
Uses Flask-Migrate (Alembic) for schema versioning:
```bash
flask db migrate -m "description"
flask db upgrade
```

### Testing Strategy
- **Unit Tests:** Focus on data validation, template rendering, and segment evaluation logic
- **Integration Tests:** Test webhook processing and campaign execution workflows
- **E2E Test:** Complete flow from webhook ingestion → campaign trigger → status callback

## Critical Patterns & Conventions

### 1. Webhook Processing
- Always store raw webhook payload first, then normalize
- Use database transactions for webhook processing to ensure data consistency
- Extract provider-specific fields: `MessageSid`, `MessageStatus`, `ErrorCode`, `From`, `WaId`

### 2. Campaign Orchestration
- Segment evaluation uses JSON DSL stored in database
- Template rendering supports `{placeholder}` substitution with user attributes
- Rate limiting enforced per campaign with Redis-backed counters
- Quiet hours respect user timezone (stored in user attributes)

### 3. Error Handling & Retries
- Failed message sends use exponential backoff via Celery retry mechanism
- Track error codes from Twilio for analytics and debugging
- Log all orchestration decisions for audit trail

### 4. API Versioning
- REST API uses `/v1/` prefix for all endpoints
- Maintain backward compatibility for webhook endpoints
- Use pagination for list endpoints (users, campaigns, messages)

## File Naming & Organization
- Models: `app/core/models/user.py`, `app/core/models/campaign.py`
- API routes: `app/api/v1/users.py`, `app/api/webhooks.py`
- Workers: `app/runner/campaign_worker.py`, `app/runner/segment_evaluator.py`
- Tests mirror source structure: `tests/api/`, `tests/core/`, `tests/runner/`

## Key Dependencies & Tools
- **Flask-SQLAlchemy** for ORM with PostgreSQL
- **Celery + Redis** for async task processing
- **Flask-Migrate** for database schema management
- **Marshmallow** for API serialization/validation
- **pytest** for testing framework
- **Twilio SDK** for WhatsApp API integration

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis broker URL
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` - Twilio credentials
- `TWILIO_PHONE_NUMBER` - WhatsApp sender number