# Event Stream Engine - Production Infrastructure
# Terraform configuration for GCP deployment

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }
  
  # Remote state backend (GCS bucket)
  backend "gcs" {
    bucket = "event-stream-engine-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Local values for resource naming
locals {
  app_name = "event-stream-engine"
  env      = var.environment
  
  # Resource naming convention
  resource_prefix = "${local.app_name}-${local.env}"
  
  # Common labels
  common_labels = {
    app         = local.app_name
    environment = local.env
    managed_by  = "terraform"
    project     = "event-stream-engine"
    version     = "v4.1.0"
  }
}