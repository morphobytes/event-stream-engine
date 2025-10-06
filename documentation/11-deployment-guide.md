# Event Stream Engine - Complete Deployment Guide

This comprehensive guide covers all deployment scenarios for Event Stream Engine, from local development to production cloud deployment on Google Cloud Platform.

## Deployment Overview

Event Stream Engine supports multiple deployment environments:

- **Local Development**: Docker Compose with local services
- **Cloud Staging**: GCP deployment for testing and UAT
- **Cloud Production**: High-availability GCP deployment with Terraform IaC

## Architecture Comparison

### Local Development Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Flask Web     │    │  Celery Worker  │    │  Celery Beat    │
│   (Port 8000)   │ <- │   (Background)  │ <- │  (Scheduler)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                        │                     │
          ▼                        ▼                     ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  PostgreSQL     │    │     Redis       │    │    Ngrok        │
│  (Port 5432)    │    │  (Port 6379)    │    │  (Webhooks)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Cloud Production Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Twilio API    │    │  Cloud Run Web  │    │ Cloud Run Worker│
│   (Webhooks)    │ -> │    Service      │ -> │     Jobs        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │  Cloud SQL      │    │  Memorystore    │
                    │  PostgreSQL     │    │     Redis       │
                    └─────────────────┘    └─────────────────┘
```

---

## Part 1: Local Development Deployment

### Prerequisites

**Required Software:**
- Docker and Docker Compose
- Python 3.11+
- Git

**Optional Tools:**
- Ngrok (for webhook testing)
- PostgreSQL client tools
- Redis CLI

### Quick Start - Local Development

```bash
# Clone the repository
git clone https://github.com/morphobytes/event-stream-engine.git
cd event-stream-engine

# Start all services with Docker Compose
docker-compose up -d

# Verify services are running
docker-compose ps

# View logs
docker-compose logs -f web
```

### Local Environment Configuration

#### 1. Environment Files Setup

**Create Local Environment Files:**
```bash
# Copy environment templates
cp .env.example .env
cp .env.dev.example .env.dev
cp .env.db.example .env.db
```

**Configure `.env` for Local Development:**
```bash
# Flask Application Configuration
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=dev_secret_key_change_in_production

# Database Configuration
DATABASE_URL=postgresql://dev_user:dev_password@db:5432/event_stream_dev

# Redis/Celery Configuration
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Twilio Configuration (Development/Sandbox)
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=+14155238886
TWILIO_WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app
```

#### 2. Docker Compose Services

The `docker-compose.yml` configures these services:

| Service | Purpose | Port | Health Check |
|---------|---------|------|--------------|
| `web` | Flask API & Webhooks | 8000 | `/health` |
| `worker` | Celery Campaign Runner | - | Process monitor |
| `scheduler` | Celery Beat Scheduler | - | Process monitor |
| `db` | PostgreSQL Database | 5432 | Connection test |
| `redis` | Message Broker & Cache | 6379 | Ping test |

#### 3. Database Setup

```bash
# Initialize database
docker-compose exec web flask db init

# Create migration
docker-compose exec web flask db migrate -m "Initial migration"

# Apply migration
docker-compose exec web flask db upgrade

# Load sample data (optional)
docker-compose exec web python -c "
from app.main import app
from app.core.data_model import db, User, Campaign
with app.app_context():
    # Create sample user
    user = User(phone_number='+1234567890', attributes={'name': 'Test User'})
    db.session.add(user)
    db.session.commit()
"
```

#### 4. Webhook Testing with Ngrok

```bash
# Install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Expose local service
ngrok http 8000

# Update Twilio webhook URLs with ngrok URL
# Inbound: https://abc123.ngrok-free.app/webhooks/inbound  
# Status: https://abc123.ngrok-free.app/webhooks/status
```

### Local Development Workflow

#### Running Services
```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up web

# View logs
docker-compose logs -f web worker

# Stop services
docker-compose down

# Restart with fresh data
docker-compose down -v && docker-compose up -d
```

#### Development Commands
```bash
# Run tests
docker-compose exec web python -m pytest

# Access Python shell
docker-compose exec web python

# Database shell
docker-compose exec db psql -U dev_user -d event_stream_dev

# Redis CLI
docker-compose exec redis redis-cli

# View Celery tasks
docker-compose exec worker celery -A app.main:celery_app inspect active
```

### Local Testing

#### API Testing
```bash
# Health check
curl http://localhost:8000/health

# List users
curl http://localhost:8000/api/v1/users

# Create campaign
curl -X POST http://localhost:8000/api/v1/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Campaign",
    "message_template": "Hello {name}!",
    "segment_criteria": {"attributes.name": {"$exists": true}}
  }'
```

#### Webhook Testing
```bash
# Test inbound webhook
curl -X POST http://localhost:8000/webhooks/inbound \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+1234567890&Body=Hello&MessageSid=SM123"

# Test status webhook  
curl -X POST http://localhost:8000/webhooks/status \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "MessageSid=SM123&MessageStatus=delivered"
```

---

## Part 2: Cloud Production Deployment

### Prerequisites

**Required Tools:**
- Google Cloud SDK (gcloud)
- Docker
- Terraform >= 1.0
- curl and jq (for testing)

**GCP Requirements:**
- GCP Project with billing enabled
- Appropriate IAM permissions (Owner or Editor role)
- API quotas sufficient for Cloud Run, Cloud SQL, etc.

### Production Architecture Components

#### Infrastructure Stack
- **Compute**: Cloud Run services (web + worker jobs)
- **Database**: Cloud SQL PostgreSQL with HA configuration
- **Cache/Broker**: Memorystore Redis with regional redundancy  
- **Networking**: VPC with private IP addresses and VPC Access Connector
- **Security**: Secret Manager, IAM service accounts, private networking
- **Storage**: Artifact Registry for container images
- **Automation**: Cloud Scheduler for campaign execution

#### Security Features
- Private VPC networking with no public database access
- Secret Manager for all sensitive credentials
- Least-privilege IAM service accounts
- Automated backups with point-in-time recovery
- SSL/TLS encryption for all communication

### Quick Start - Cloud Deployment

```bash
# Clone and prepare
git clone https://github.com/morphobytes/event-stream-engine.git
cd event-stream-engine

# Run automated deployment
chmod +x scripts/deploy.sh
./scripts/deploy.sh YOUR_GCP_PROJECT_ID us-central1 v4.1.0

# Configure post-deployment
chmod +x scripts/post-deploy.sh  
./scripts/post-deploy.sh YOUR_GCP_PROJECT_ID
```

### Manual Cloud Deployment

#### Step 1: GCP Project Setup

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  servicenetworking.googleapis.com \
  redis.googleapis.com \
  cloudscheduler.googleapis.com \
  compute.googleapis.com \
  vpcaccess.googleapis.com
```

#### Step 2: Configure Terraform Variables

```bash
cd terraform

# Create configuration file
cat > terraform.tfvars <<EOF
project_id         = "your-gcp-project-id"
region            = "us-central1"
zone              = "us-central1-a"
environment       = "prod"

# Database configuration  
db_instance_tier     = "db-custom-2-7680"  # 2 vCPU, 7.5GB RAM
redis_memory_size_gb = 4

# Container image (update after building)
container_image = "us-central1-docker.pkg.dev/your-project/event-stream-engine-prod-containers/event-stream-engine:v4.1.0"

# Twilio configuration
twilio_phone_number = "whatsapp:+14155552671"  
twilio_account_sid  = "your_twilio_account_sid"
twilio_auth_token   = "your_twilio_auth_token"

# Scaling configuration
min_web_instances = 2
max_web_instances = 50

# Safety configuration
enable_deletion_protection = true
EOF
```

#### Step 3: Build and Store Container Image

```bash
# Build production image
docker build -t event-stream-engine:v4.1.0 .

# Configure Artifact Registry authentication
gcloud auth configure-docker us-central1-docker.pkg.dev

# Tag and push (after Terraform creates the registry)
REGISTRY_URL="us-central1-docker.pkg.dev/YOUR_PROJECT/event-stream-engine-prod-containers"
docker tag event-stream-engine:v4.1.0 $REGISTRY_URL/event-stream-engine:v4.1.0
docker push $REGISTRY_URL/event-stream-engine:v4.1.0
```

#### Step 4: Deploy Infrastructure with Terraform

```bash
# Create remote state bucket
gsutil mb gs://YOUR_PROJECT_ID-terraform-state
gsutil versioning set on gs://YOUR_PROJECT_ID-terraform-state

# Initialize Terraform
terraform init \
  -backend-config="bucket=YOUR_PROJECT_ID-terraform-state" \
  -backend-config="prefix=terraform/state"

# Plan deployment
terraform plan -out=deployment.tfplan

# Apply deployment
terraform apply deployment.tfplan
```

#### Step 5: Verify and Configure

```bash
# Get deployment information
terraform output deployment_summary

# Test health endpoint
WEB_URL=$(terraform output -raw web_service_url)
curl $WEB_URL/health

# Configure Twilio webhooks with output URLs
terraform output twilio_webhook_urls
```

### Production Configuration Management

#### Environment Variables in Cloud

The Terraform deployment automatically configures:

| Variable | Source | Purpose |
|----------|--------|---------|
| `DATABASE_URL` | Auto-generated | PostgreSQL connection |
| `REDIS_URL` | Auto-generated | Redis connection |  
| `SECRET_KEY` | Secret Manager | Flask session security |
| `TWILIO_ACCOUNT_SID` | Secret Manager | Twilio authentication |
| `TWILIO_AUTH_TOKEN` | Secret Manager | Twilio authentication |
| `TWILIO_PHONE_NUMBER` | Terraform variable | WhatsApp number |
| `GOOGLE_CLOUD_PROJECT` | Auto-detected | GCP project ID |

#### Scaling Configuration

**Auto-scaling Parameters:**
```hcl
# Cloud Run scaling
min_web_instances = 2      # Always-on instances
max_web_instances = 50     # Scale up to 50 instances
max_instance_request_concurrency = 100  # Requests per instance

# Database scaling  
db_instance_tier = "db-custom-4-15360"  # 4 vCPU, 15GB RAM
availability_type = "REGIONAL"           # Multi-zone HA

# Redis scaling
redis_memory_size_gb = 8    # 8GB memory
tier = "STANDARD_HA"        # High availability
```

#### Security Configuration

**Network Security:**
- All database traffic over private VPC
- VPC Access Connector for serverless services  
- Firewall rules limited to health checks
- No public IP addresses on databases

**Credential Management:**
- All secrets stored in Google Secret Manager
- IAM service accounts with minimal permissions
- Automatic secret rotation support
- Audit logging for all secret access

### Production Operations

#### Monitoring and Logging

```bash
# View application logs
gcloud run services logs read event-stream-engine-prod-web --region=us-central1

# Monitor service metrics  
gcloud run services describe event-stream-engine-prod-web --region=us-central1

# Database monitoring
gcloud sql instances describe event-stream-engine-prod-db

# Redis monitoring  
gcloud redis instances describe event-stream-engine-prod-redis --region=us-central1
```

#### Database Operations

```bash
# Connect to database
gcloud sql connect event-stream-engine-prod-db --user=app_user

# Create backup
gcloud sql backups create --instance=event-stream-engine-prod-db

# View backups
gcloud sql backups list --instance=event-stream-engine-prod-db

# Point-in-time recovery
gcloud sql instances clone event-stream-engine-prod-db recovery-instance \
  --point-in-time='2023-10-05T10:30:00Z'
```

#### Application Updates

```bash
# Build new version
docker build -t event-stream-engine:v4.2.0 .

# Tag and push
docker tag event-stream-engine:v4.2.0 $REGISTRY_URL/event-stream-engine:v4.2.0
docker push $REGISTRY_URL/event-stream-engine:v4.2.0

# Update Terraform configuration
sed -i 's/v4.1.0/v4.2.0/' terraform.tfvars

# Deploy update
terraform plan -out=update.tfplan
terraform apply update.tfplan
```

### Cost Optimization

#### Resource Right-Sizing

**Development Environment:**
```hcl
db_instance_tier = "db-f1-micro"        # $7/month  
redis_memory_size_gb = 1                # $30/month
min_web_instances = 0                   # Scale to zero
max_web_instances = 5                   # Limit scaling
```

**Production Environment:**
```hcl  
db_instance_tier = "db-custom-2-7680"   # $150/month
redis_memory_size_gb = 4                # $120/month  
min_web_instances = 2                   # Always available
max_web_instances = 50                  # Handle traffic spikes
```

#### Cost Monitoring

```bash
# View billing information
gcloud billing accounts list
gcloud billing projects link YOUR_PROJECT_ID --billing-account=ACCOUNT_ID

# Set up budget alerts
gcloud billing budgets create \
  --billing-account=ACCOUNT_ID \
  --display-name="Event Stream Engine Budget" \
  --budget-amount=200USD \
  --threshold-percent=50,90,100
```

---

## Part 3: Decommissioning and Cleanup

### Complete Infrastructure Cleanup

#### Automated Decommissioning

```bash
# Remove infrastructure only (keep project)
./scripts/decommission.sh YOUR_PROJECT_ID no

# Remove infrastructure AND delete entire project  
./scripts/decommission.sh YOUR_PROJECT_ID yes
```

#### Manual Cleanup Process

```bash
# Disable deletion protection
cd terraform
sed -i 's/enable_deletion_protection = true/enable_deletion_protection = false/' terraform.tfvars
terraform apply -auto-approve

# Destroy infrastructure
terraform destroy -auto-approve

# Clean up remaining resources
gcloud run services list --format="value(metadata.name)" | \
  grep event-stream | xargs -I {} gcloud run services delete {} --region=us-central1 --quiet

# Delete secrets
gcloud secrets list --format="value(name)" | \
  grep event-stream | xargs -I {} gcloud secrets delete {} --quiet

# Remove state bucket
gsutil rm -r gs://YOUR_PROJECT_ID-terraform-state
```

### Local Environment Cleanup

```bash
# Stop and remove containers
docker-compose down -v

# Remove images
docker rmi $(docker images event-stream-engine -q)

# Clean up Docker system
docker system prune -f
```

---

## Part 4: Troubleshooting

### Common Local Issues

#### Docker Compose Issues
```bash
# Port conflicts
netstat -tlnp | grep :8000
docker-compose down && docker-compose up -d

# Database connection issues  
docker-compose logs db
docker-compose exec db psql -U dev_user -l

# Redis connection issues
docker-compose logs redis
docker-compose exec redis redis-cli ping
```

#### Environment Variable Issues
```bash
# Check loaded variables
docker-compose exec web env | grep -E "(DATABASE|REDIS|TWILIO)"

# Reload environment
docker-compose down && docker-compose up -d
```

### Common Cloud Issues

#### Deployment Issues
```bash
# Check Terraform state
terraform show
terraform refresh

# Verify APIs are enabled
gcloud services list --enabled | grep -E "(run|sql|redis)"

# Check IAM permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID
```

#### Service Issues  
```bash
# Cloud Run not starting
gcloud run services logs read SERVICE_NAME --region=REGION

# Database connection issues
gcloud sql instances describe INSTANCE_NAME
gcloud compute networks vpc-access connectors describe CONNECTOR_NAME --region=REGION

# Secret Manager issues
gcloud secrets list | grep event-stream
gcloud secrets get-iam-policy SECRET_NAME
```

#### Performance Issues
```bash
# Check Cloud Run metrics
gcloud run services describe SERVICE_NAME --region=REGION

# Database performance
gcloud sql instances describe INSTANCE_NAME --format="value(stats)"

# Redis performance  
gcloud redis instances describe INSTANCE_NAME --region=REGION
```

### Debug Commands Reference

#### Local Development
```bash
# Service status
docker-compose ps

# Live logs
docker-compose logs -f SERVICE_NAME

# Execute commands in container
docker-compose exec SERVICE_NAME COMMAND

# Database queries
docker-compose exec db psql -U dev_user -d event_stream_dev -c "SELECT COUNT(*) FROM users;"

# Redis inspection
docker-compose exec redis redis-cli keys "*"
```

#### Cloud Production
```bash
# Service logs
gcloud run services logs read SERVICE_NAME --region=REGION --limit=100

# Database logs  
gcloud sql instances logs list INSTANCE_NAME
gcloud sql instances logs download INSTANCE_NAME LOG_FILE

# Execute database queries
gcloud sql connect INSTANCE_NAME --user=USER_NAME

# Redis metrics
gcloud redis instances describe INSTANCE_NAME --region=REGION
```

---

## Part 5: Advanced Configuration

### Multi-Environment Setup

#### Environment-Specific Configurations

**Development (`dev.tfvars`):**
```hcl
environment = "dev"
db_instance_tier = "db-f1-micro"
redis_memory_size_gb = 1
min_web_instances = 0
max_web_instances = 3
enable_deletion_protection = false
```

**Staging (`staging.tfvars`):**
```hcl  
environment = "staging"
db_instance_tier = "db-custom-1-3840"
redis_memory_size_gb = 2
min_web_instances = 1
max_web_instances = 10
enable_deletion_protection = true
```

**Production (`prod.tfvars`):**
```hcl
environment = "prod"  
db_instance_tier = "db-custom-4-15360"
redis_memory_size_gb = 8
min_web_instances = 3
max_web_instances = 100
enable_deletion_protection = true
```

#### Deploy Multiple Environments
```bash
# Deploy to different environments
terraform workspace new dev
terraform apply -var-file="dev.tfvars"

terraform workspace new staging  
terraform apply -var-file="staging.tfvars"

terraform workspace new prod
terraform apply -var-file="prod.tfvars"
```

### Custom Domain Configuration

```bash
# Map custom domain to Cloud Run
gcloud run domain-mappings create \
  --service=event-stream-engine-prod-web \
  --domain=api.yourdomain.com \
  --region=us-central1

# Configure DNS records (add to your DNS provider)
# Type: CNAME
# Name: api
# Value: ghs.googlehosted.com

# Verify domain mapping
gcloud run domain-mappings describe --domain=api.yourdomain.com --region=us-central1
```

### CI/CD Pipeline Setup

#### GitHub Actions Workflow
```yaml
# .github/workflows/deploy.yml  
name: Deploy Event Stream Engine
on:
  push:
    branches: [main]
    
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Google Cloud
        uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          
      - name: Deploy to Cloud Run
        run: |
          ./scripts/deploy.sh ${{ secrets.GCP_PROJECT_ID }} us-central1 ${GITHUB_SHA::8}
```

#### Cloud Build Integration  
```bash
# Connect repository to Cloud Build
gcloud builds submit --config=cloudbuild.yaml

# Set up build triggers
gcloud builds triggers create github \
  --repo-name=event-stream-engine \
  --repo-owner=morphobytes \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

---

**This complete deployment guide covers all scenarios from local development to production cloud deployment. Choose the appropriate section based on your deployment needs and follow the step-by-step instructions for your target environment.**