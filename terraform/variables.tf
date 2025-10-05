# Terraform variables for Event Stream Engine deployment

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resource deployment"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone for resource deployment"
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Environment name (prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "db_instance_tier" {
  description = "Cloud SQL instance machine type"
  type        = string
  default     = "db-custom-1-3840"  # 1 vCPU, 3.75GB RAM for production
}

variable "redis_memory_size_gb" {
  description = "Memorystore Redis memory size in GB"
  type        = number
  default     = 2
}

variable "container_image" {
  description = "Container image URL in Artifact Registry"
  type        = string
}

variable "twilio_phone_number" {
  description = "Twilio WhatsApp phone number"
  type        = string
}

variable "twilio_account_sid" {
  description = "Twilio Account SID (will be stored in Secret Manager)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "twilio_auth_token" {
  description = "Twilio Auth Token (will be stored in Secret Manager)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "domain_name" {
  description = "Custom domain for the application (optional)"
  type        = string
  default     = ""
}

variable "min_web_instances" {
  description = "Minimum number of web service instances"
  type        = number
  default     = 1
}

variable "max_web_instances" {
  description = "Maximum number of web service instances"
  type        = number
  default     = 10
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection for critical resources"
  type        = bool
  default     = true
}