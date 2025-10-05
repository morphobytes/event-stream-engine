# Environment Setup & Configuration

## 🚀 Quick Start Guide

Complete setup instructions for local development, Docker deployment, and production configuration of the Event Stream Engine.

## 📋 Prerequisites

### **System Requirements**
- **Python 3.9+** with pip package manager
- **Docker & Docker Compose** for containerized development
- **PostgreSQL 13+** or Docker container
- **Redis 6+** or Docker container
- **Git** for version control

### **External Services**
- **Twilio Account** with WhatsApp API access
- **Google Cloud Platform** account (for production deployment)

---

## 🛠️ Local Development Setup

### **1. Repository Clone & Setup**
```bash
# Clone the repository
git clone <repository-url> event-stream-engine
cd event-stream-engine

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### **2. Environment Configuration**
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
vim .env  # or your preferred editor
```

### **3. Environment Variables**
```bash
# .env file configuration

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/event_stream_engine
SQLALCHEMY_DATABASE_URI=${DATABASE_URL}

# Redis Configuration  
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=${REDIS_URL}

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here  
TWILIO_PHONE_NUMBER=+1234567890

# Flask Configuration
FLASK_APP=app.main:create_app
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Logging Configuration
LOG_LEVEL=DEBUG
```

### **4. Docker Development Environment**
```bash
# Start all services (PostgreSQL, Redis, Celery)
docker-compose up -d

# Verify services are running
docker-compose ps

# View logs
docker-compose logs -f
```

### **5. Database Setup**
```bash
# Initialize database schema
flask db upgrade

# Create sample data (optional)
flask seed-data  # If seeding script exists
```

### **6. Start Development Server**
```bash
# Start Flask development server
flask run --host=0.0.0.0 --port=5000

# Application available at:
# http://localhost:5000 (Web UI)
# http://localhost:5000/api/v1/ (API endpoints)
# http://localhost:5000/health (Health check)
```

---

## 🐳 Docker Deployment

### **Complete Docker Stack**
```yaml
# docker-compose.yml - Production configuration
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/event_stream_engine
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    image: postgres:13
    environment:
      POSTGRES_DB: event_stream_engine
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    volumes:
      - redis_data:/data

  worker:
    build: .
    command: celery -A app.main.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/event_stream_engine
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
  redis_data:
```

### **Production Dockerfile**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Expose port
EXPOSE 8080

# Start application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "app.main:create_app()"]
```

---

## ☁️ Google Cloud Platform Deployment

### **Cloud Run Deployment**
```bash
# Build and deploy to Cloud Run
gcloud builds submit --tag gcr.io/PROJECT_ID/event-stream-engine
gcloud run deploy event-stream-engine \
  --image gcr.io/PROJECT_ID/event-stream-engine \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### **Cloud SQL Setup**
```bash
# Create PostgreSQL instance
gcloud sql instances create event-stream-db \
  --database-version=POSTGRES_13 \
  --tier=db-f1-micro \
  --region=us-central1

# Create database
gcloud sql databases create event_stream_engine \
  --instance=event-stream-db

# Create user
gcloud sql users create appuser \
  --instance=event-stream-db \
  --password=secure_password
```

### **Redis Memorystore Setup**
```bash
# Create Redis instance
gcloud redis instances create event-stream-cache \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_6_x
```

### **Production Environment Variables**
```bash
# Set Cloud Run environment variables
gcloud run services update event-stream-engine \
  --set-env-vars="
DATABASE_URL=postgresql://appuser:password@/event_stream_engine?host=/cloudsql/PROJECT_ID:us-central1:event-stream-db,
REDIS_URL=redis://REDIS_IP:6379/0,
TWILIO_ACCOUNT_SID=your_account_sid,
TWILIO_AUTH_TOKEN=your_auth_token,
TWILIO_PHONE_NUMBER=+1234567890
"
```

---

## 🔧 Development Workflow

### **Database Migrations**
```bash
# Create new migration
flask db migrate -m "Add new feature"

# Apply migrations
flask db upgrade

# Rollback migration
flask db downgrade
```

### **Code Quality Tools**
```bash
# Format code with Black
black app/ --line-length=88

# Check style with flake8
flake8 app/ --max-line-length=88 --extend-ignore=E203,W503

# Type checking with mypy
mypy app/ --ignore-missing-imports

# Sort imports
isort app/
```

### **Testing**
```bash
# Run integration tests
python tests/integration_test_suite.py

# Run specific test modules
python -m pytest tests/test_api.py -v

# Check test coverage
coverage run -m pytest
coverage report -m
```

---

## 🛡️ Security Configuration

### **Environment Security**
- **Secret Management**: Use environment variables, never commit secrets
- **Database Security**: Strong passwords, connection encryption
- **API Security**: Rate limiting, input validation
- **Network Security**: VPC configuration, firewall rules

### **Production Security Checklist**
- ✅ Environment variables for all secrets
- ✅ Database connection encryption (SSL)
- ✅ API rate limiting configured
- ✅ Input validation on all endpoints
- ✅ HTTPS/TLS encryption enabled
- ✅ Regular security updates applied

---

## 🔍 Troubleshooting

### **Common Issues**

#### **Database Connection Issues**
```bash
# Check database connectivity
psql $DATABASE_URL -c "SELECT 1;"

# Verify database schema
flask db current
flask db show
```

#### **Redis Connection Issues**
```bash
# Test Redis connectivity
redis-cli -u $REDIS_URL ping

# Check Redis memory usage
redis-cli -u $REDIS_URL info memory
```

#### **Celery Worker Issues**
```bash
# Start Celery worker with debug info
celery -A app.main.celery_app worker --loglevel=debug

# Monitor Celery tasks
celery -A app.main.celery_app flower
```

#### **Twilio Integration Issues**
```bash
# Test Twilio credentials
curl -X GET "https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID.json" \
  -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN

# Verify WhatsApp sender number
curl -X GET "https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID/IncomingPhoneNumbers.json" \
  -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN
```

### **Performance Monitoring**
```bash
# Monitor application performance
# Database query performance
SELECT query, total_time, calls, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC LIMIT 10;

# Memory usage monitoring  
ps aux | grep python
top -p $(pgrep -f "flask|gunicorn")
```

---

*This comprehensive setup guide ensures reliable deployment and operation of the Event Stream Engine across all environments from local development to production cloud deployment.*
