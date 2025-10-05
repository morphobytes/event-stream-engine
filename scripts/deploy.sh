#!/bin/bash
# Event Stream Engine - Production deployment script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
PROJECT_ID=${1}
REGION=${2:-"us-central1"}
IMAGE_TAG=${3:-"v4.1.0"}

if [ -z "$PROJECT_ID" ]; then
    log_error "Usage: $0 <project_id> [region] [image_tag]"
    log_info "Example: $0 my-gcp-project us-central1 v4.1.0"
    exit 1
fi

log_info "Starting Event Stream Engine deployment..."
log_info "Project: $PROJECT_ID"
log_info "Region: $REGION"
log_info "Image Tag: $IMAGE_TAG"

# Check prerequisites
log_info "Checking prerequisites..."

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI is required but not installed"
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is required but not installed"
    exit 1
fi

# Check if terraform is installed
if ! command -v terraform &> /dev/null; then
    log_error "Terraform is required but not installed"
    exit 1
fi

# Set the active project
log_info "Setting active GCP project..."
gcloud config set project $PROJECT_ID

# Enable billing (user must do this manually)
log_warning "Please ensure billing is enabled for project $PROJECT_ID"

# Create remote state bucket
log_info "Creating Terraform state bucket..."
BUCKET_NAME="$PROJECT_ID-terraform-state"
gsutil mb gs://$BUCKET_NAME || log_info "Bucket already exists"
gsutil versioning set on gs://$BUCKET_NAME
gsutil lifecycle set - gs://$BUCKET_NAME <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 365,
          "isLive": false
        }
      }
    ]
  }
}
EOF

# Build and push container image
log_info "Building and pushing container image..."
ARTIFACT_REGISTRY_URL="$REGION-docker.pkg.dev/$PROJECT_ID/event-stream-engine-prod-containers"

# Build the image
log_info "Building Docker image..."
docker build -t event-stream-engine:$IMAGE_TAG .

# Tag for Artifact Registry
docker tag event-stream-engine:$IMAGE_TAG $ARTIFACT_REGISTRY_URL/event-stream-engine:$IMAGE_TAG

# Configure Docker for Artifact Registry
log_info "Configuring Docker authentication..."
gcloud auth configure-docker $REGION-docker.pkg.dev --quiet

# Get Twilio credentials from user
log_info "Twilio configuration required..."
read -p "Enter Twilio Account SID: " TWILIO_ACCOUNT_SID
read -s -p "Enter Twilio Auth Token: " TWILIO_AUTH_TOKEN
echo
read -p "Enter Twilio Phone Number (format: whatsapp:+1234567890): " TWILIO_PHONE_NUMBER

# Create terraform.tfvars file
log_info "Creating Terraform variables file..."
cd terraform

cat > terraform.tfvars <<EOF
project_id         = "$PROJECT_ID"
region            = "$REGION"
zone              = "$REGION-a"
environment       = "prod"

# Database configuration
db_instance_tier     = "db-custom-1-3840"
redis_memory_size_gb = 2

# Container image
container_image = "$ARTIFACT_REGISTRY_URL/event-stream-engine:$IMAGE_TAG"

# Twilio configuration
twilio_phone_number = "$TWILIO_PHONE_NUMBER"
twilio_account_sid  = "$TWILIO_ACCOUNT_SID"
twilio_auth_token   = "$TWILIO_AUTH_TOKEN"

# Scaling configuration
min_web_instances = 1
max_web_instances = 10

# Safety configuration
enable_deletion_protection = true
EOF

# Initialize Terraform
log_info "Initializing Terraform..."
terraform init \
  -backend-config="bucket=$BUCKET_NAME" \
  -backend-config="prefix=terraform/state"

# Validate configuration
log_info "Validating Terraform configuration..."
terraform validate

# Plan deployment
log_info "Creating Terraform plan..."
terraform plan -out=tfplan

# Confirm deployment
log_warning "Review the plan above. Do you want to proceed with deployment?"
read -p "Type 'yes' to continue: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log_error "Deployment cancelled by user"
    exit 1
fi

# Apply deployment
log_info "Applying Terraform plan..."
terraform apply tfplan

# Push the container image (after Artifact Registry is created)
log_info "Pushing container image to Artifact Registry..."
docker push $ARTIFACT_REGISTRY_URL/event-stream-engine:$IMAGE_TAG

# Get outputs
log_info "Deployment completed! Getting service information..."
WEB_SERVICE_URL=$(terraform output -raw web_service_url)
INBOUND_WEBHOOK_URL=$(terraform output -json twilio_webhook_urls | jq -r '.inbound_webhook')
STATUS_WEBHOOK_URL=$(terraform output -json twilio_webhook_urls | jq -r '.status_webhook')
HEALTH_CHECK_URL="$WEB_SERVICE_URL/health"

# Test the deployment
log_info "Testing deployment..."
if curl -f -s "$HEALTH_CHECK_URL" > /dev/null; then
    log_success "Health check passed!"
else
    log_warning "Health check failed. Service may still be starting up."
fi

cd ..

# Display deployment summary
echo
log_success "==============================================="
log_success "Event Stream Engine Deployment Complete!"
log_success "==============================================="
echo
log_info "Service Information:"
echo "  Web Service URL: $WEB_SERVICE_URL"
echo "  Health Check: $HEALTH_CHECK_URL"
echo "  API Documentation: $WEB_SERVICE_URL/api/v1/docs"
echo
log_info "Twilio Webhook Configuration:"
echo "  Inbound Webhook URL: $INBOUND_WEBHOOK_URL"
echo "  Status Webhook URL: $STATUS_WEBHOOK_URL"
echo
log_info "Next Steps:"
echo "  1. Configure Twilio webhooks with the URLs above"
echo "  2. Test webhook endpoints with Twilio"
echo "  3. Run database migrations (see post-deployment script)"
echo "  4. Monitor application logs and metrics"
echo
log_warning "Important: Save the webhook URLs for Twilio configuration!"

# Save deployment info to file
cat > deployment-info.txt <<EOF
Event Stream Engine - Deployment Information
Deployed: $(date)
Project: $PROJECT_ID
Region: $REGION

Service URLs:
- Web Service: $WEB_SERVICE_URL
- Health Check: $HEALTH_CHECK_URL
- API Docs: $WEB_SERVICE_URL/api/v1/docs

Twilio Webhooks:
- Inbound: $INBOUND_WEBHOOK_URL
- Status: $STATUS_WEBHOOK_URL

Container Image: $ARTIFACT_REGISTRY_URL/event-stream-engine:$IMAGE_TAG
EOF

log_success "Deployment information saved to deployment-info.txt"