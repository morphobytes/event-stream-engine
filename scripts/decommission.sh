#!/bin/bash
# Event Stream Engine - Complete Decommissioning Script
# This script will destroy ALL infrastructure and optionally delete the entire GCP project

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
DELETE_PROJECT=${2:-"no"}

if [ -z "$PROJECT_ID" ]; then
    log_error "Usage: $0 <project_id> [delete_project]"
    log_info "Examples:"
    log_info "  $0 my-gcp-project no           # Destroy infrastructure only"
    log_info "  $0 my-gcp-project yes          # Destroy infrastructure AND delete project"
    exit 1
fi

log_warning "==============================================="
log_warning "Event Stream Engine DECOMMISSIONING"
log_warning "==============================================="
log_warning "Project: $PROJECT_ID"
log_warning "Delete Project: $DELETE_PROJECT"
log_warning "==============================================="

# Confirm destructive action
log_error "This will PERMANENTLY DELETE all Event Stream Engine infrastructure!"
if [ "$DELETE_PROJECT" = "yes" ]; then
    log_error "THIS WILL ALSO DELETE THE ENTIRE GCP PROJECT!"
fi
log_warning "This action cannot be undone!"
echo
read -p "Type 'DELETE' to confirm complete destruction: " CONFIRM

if [ "$CONFIRM" != "DELETE" ]; then
    log_info "Decommissioning cancelled by user"
    exit 0
fi

# Set the active project
log_info "Setting active GCP project..."
gcloud config set project $PROJECT_ID

# Phase 1: Disable deletion protection (if enabled)
log_info "Phase 1: Disabling deletion protection..."
cd terraform

# Check if terraform state exists
if [ -f ".terraform/terraform.tfstate" ] || [ -f "terraform.tfstate" ]; then
    log_info "Disabling deletion protection on critical resources..."
    
    # Update variables to disable deletion protection
    if [ -f "terraform.tfvars" ]; then
        sed -i 's/enable_deletion_protection = true/enable_deletion_protection = false/' terraform.tfvars
        
        # Apply changes to remove deletion protection
        terraform plan -out=disable-protection-plan
        terraform apply -auto-approve disable-protection-plan
        
        log_success "Deletion protection disabled"
    else
        log_warning "No terraform.tfvars found, assuming protection already disabled"
    fi
else
    log_warning "No Terraform state found, skipping protection removal"
fi

# Phase 2: Destroy Terraform-managed infrastructure
log_info "Phase 2: Destroying Terraform infrastructure..."

if [ -f ".terraform/terraform.tfstate" ] || [ -f "terraform.tfstate" ]; then
    log_info "Destroying all Terraform-managed resources..."
    terraform destroy -auto-approve
    
    log_success "Terraform infrastructure destroyed"
else
    log_warning "No Terraform state found"
fi

cd ..

# Phase 3: Clean up remaining resources manually
log_info "Phase 3: Cleaning up remaining resources..."

# Delete any remaining Cloud Run services
log_info "Cleaning up remaining Cloud Run services..."
gcloud run services list --region=us-central1 --format="value(metadata.name)" 2>/dev/null | while read service; do
    if [[ $service == *"event-stream-engine"* ]]; then
        log_info "Deleting Cloud Run service: $service"
        gcloud run services delete $service --region=us-central1 --quiet || true
    fi
done

# Delete any remaining Cloud Run jobs
log_info "Cleaning up remaining Cloud Run jobs..."
gcloud run jobs list --region=us-central1 --format="value(metadata.name)" 2>/dev/null | while read job; do
    if [[ $job == *"event-stream-engine"* ]]; then
        log_info "Deleting Cloud Run job: $job"
        gcloud run jobs delete $job --region=us-central1 --quiet || true
    fi
done

# Delete Cloud Scheduler jobs
log_info "Cleaning up Cloud Scheduler jobs..."
gcloud scheduler jobs list --location=us-central1 --format="value(name)" 2>/dev/null | while read job; do
    if [[ $job == *"event-stream-engine"* ]]; then
        log_info "Deleting scheduler job: $(basename $job)"
        gcloud scheduler jobs delete $(basename $job) --location=us-central1 --quiet || true
    fi
done

# Delete Artifact Registry repositories
log_info "Cleaning up Artifact Registry repositories..."
gcloud artifacts repositories list --location=us-central1 --format="value(name)" 2>/dev/null | while read repo; do
    if [[ $repo == *"event-stream-engine"* ]]; then
        log_info "Deleting Artifact Registry repository: $(basename $repo)"
        gcloud artifacts repositories delete $(basename $repo) --location=us-central1 --quiet || true
    fi
done

# Delete Secret Manager secrets
log_info "Cleaning up Secret Manager secrets..."
gcloud secrets list --format="value(name)" 2>/dev/null | while read secret; do
    if [[ $secret == *"event-stream-engine"* ]]; then
        log_info "Deleting secret: $secret"
        gcloud secrets delete $secret --quiet || true
    fi
done

# Delete VPC and networking
log_info "Cleaning up VPC and networking resources..."
# Delete VPC access connectors
gcloud compute networks vpc-access connectors list --region=us-central1 --format="value(name)" 2>/dev/null | while read connector; do
    if [[ $connector == *"event-stream-engine"* ]]; then
        log_info "Deleting VPC connector: $connector"
        gcloud compute networks vpc-access connectors delete $connector --region=us-central1 --quiet || true
    fi
done

# Delete firewall rules
gcloud compute firewall-rules list --format="value(name)" 2>/dev/null | while read rule; do
    if [[ $rule == *"event-stream-engine"* ]]; then
        log_info "Deleting firewall rule: $rule"
        gcloud compute firewall-rules delete $rule --quiet || true
    fi
done

# Delete VPC networks (after all dependent resources are gone)
gcloud compute networks list --format="value(name)" 2>/dev/null | while read network; do
    if [[ $network == *"event-stream-engine"* ]]; then
        log_info "Deleting VPC network: $network"
        gcloud compute networks delete $network --quiet || true
    fi
done

# Delete IAM service accounts
log_info "Cleaning up IAM service accounts..."
gcloud iam service-accounts list --format="value(email)" 2>/dev/null | while read sa; do
    if [[ $sa == *"event-stream-engine"* ]]; then
        log_info "Deleting service account: $sa"
        gcloud iam service-accounts delete $sa --quiet || true
    fi
done

# Phase 4: Clean up Terraform state
log_info "Phase 4: Cleaning up Terraform state..."

# Delete remote state bucket
BUCKET_NAME="$PROJECT_ID-terraform-state"
log_info "Deleting Terraform state bucket: $BUCKET_NAME"
gsutil rm -r gs://$BUCKET_NAME 2>/dev/null || log_warning "State bucket not found or already deleted"

# Clean local Terraform state
if [ -d "terraform/.terraform" ]; then
    log_info "Cleaning local Terraform state..."
    rm -rf terraform/.terraform
    rm -f terraform/terraform.tfstate*
    rm -f terraform/tfplan
    rm -f terraform/*.backup
fi

# Phase 5: Delete entire project (if requested)
if [ "$DELETE_PROJECT" = "yes" ]; then
    log_warning "Phase 5: Deleting entire GCP project..."
    log_error "Last chance to cancel! This will delete project $PROJECT_ID permanently!"
    read -p "Type 'DELETE PROJECT' to confirm: " FINAL_CONFIRM
    
    if [ "$FINAL_CONFIRM" = "DELETE PROJECT" ]; then
        log_info "Deleting GCP project: $PROJECT_ID"
        gcloud projects delete $PROJECT_ID --quiet
        
        log_success "Project $PROJECT_ID has been deleted"
        log_info "It may take a few minutes for the deletion to complete"
    else
        log_info "Project deletion cancelled"
    fi
fi

# Phase 6: Cleanup completion
log_success "==============================================="
log_success "Decommissioning Complete!"
log_success "==============================================="

if [ "$DELETE_PROJECT" = "yes" ]; then
    log_info "Project $PROJECT_ID has been scheduled for deletion"
    log_info "The project will be permanently deleted within a few minutes"
else
    log_info "All Event Stream Engine infrastructure has been destroyed"
    log_info "Project $PROJECT_ID remains active but cleaned up"
fi

log_info "Local Terraform state has been cleaned up"
log_warning "If you plan to redeploy, you'll need to run the full deployment process again"

# Create decommission log
cat > decommission-log.txt <<EOF
Event Stream Engine - Decommissioning Log
Completed: $(date)
Project: $PROJECT_ID
Project Deleted: $DELETE_PROJECT

Actions Taken:
- Disabled deletion protection
- Destroyed Terraform infrastructure
- Cleaned up remaining Cloud resources
- Deleted IAM service accounts
- Removed VPC and networking
- Deleted Artifact Registry repositories
- Removed Secret Manager secrets
- Cleaned Terraform state
$([ "$DELETE_PROJECT" = "yes" ] && echo "- Deleted entire GCP project")

Status: COMPLETE
EOF

log_info "Decommissioning log saved to decommission-log.txt"