#!/bin/bash
# Event Stream Engine - Post-deployment configuration script

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

PROJECT_ID=${1}

if [ -z "$PROJECT_ID" ]; then
    log_error "Usage: $0 <project_id>"
    exit 1
fi

log_info "Running post-deployment configuration for project: $PROJECT_ID"

# Set the active project
gcloud config set project $PROJECT_ID

cd terraform

# Get deployment information
log_info "Getting deployment information..."
WEB_SERVICE_URL=$(terraform output -raw web_service_url 2>/dev/null || echo "")

if [ -z "$WEB_SERVICE_URL" ]; then
    log_error "Could not get web service URL. Is the deployment complete?"
    exit 1
fi

log_info "Web Service URL: $WEB_SERVICE_URL"

# Run database migrations
log_info "Running database migrations..."
MIGRATION_URL="$WEB_SERVICE_URL/api/v1/internal/migrate-database"

# Trigger migration via HTTP endpoint
curl -X POST \
    -H "Content-Type: application/json" \
    -d '{"action": "migrate"}' \
    "$MIGRATION_URL" || log_warning "Migration endpoint not available yet"

# Test health endpoint
log_info "Testing health endpoint..."
HEALTH_URL="$WEB_SERVICE_URL/health"

for i in {1..30}; do
    if curl -f -s "$HEALTH_URL" > /dev/null; then
        log_success "Health check passed!"
        break
    else
        log_info "Waiting for service to be ready... (attempt $i/30)"
        sleep 10
    fi
done

# Test API endpoints
log_info "Testing API endpoints..."
API_URL="$WEB_SERVICE_URL/api/v1"

# Test users endpoint
curl -f -s "$API_URL/users?limit=1" > /dev/null && log_success "Users API working" || log_warning "Users API not accessible"

# Test campaigns endpoint  
curl -f -s "$API_URL/campaigns?limit=1" > /dev/null && log_success "Campaigns API working" || log_warning "Campaigns API not accessible"

# Display webhook URLs
log_info "Webhook URLs for Twilio configuration:"
INBOUND_WEBHOOK_URL=$(terraform output -json twilio_webhook_urls | jq -r '.inbound_webhook')
STATUS_WEBHOOK_URL=$(terraform output -json twilio_webhook_urls | jq -r '.status_webhook')

echo "  Inbound Webhook: $INBOUND_WEBHOOK_URL"
echo "  Status Webhook: $STATUS_WEBHOOK_URL"

# Test webhook endpoints
log_info "Testing webhook endpoints..."
curl -f -s -X POST "$INBOUND_WEBHOOK_URL" -d "test=1" > /dev/null && log_success "Inbound webhook accessible" || log_warning "Inbound webhook not accessible"
curl -f -s -X POST "$STATUS_WEBHOOK_URL" -d "test=1" > /dev/null && log_success "Status webhook accessible" || log_warning "Status webhook not accessible"

cd ..

log_success "Post-deployment configuration complete!"
log_info "Your Event Stream Engine is ready for production use."

echo
log_info "Next Steps:"
echo "  1. Configure Twilio webhooks with the URLs above"
echo "  2. Test sending messages through the system"
echo "  3. Monitor application logs and metrics"
echo "  4. Set up alerting and monitoring dashboards"