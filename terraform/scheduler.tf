# Cloud Scheduler for campaign automation

resource "google_cloud_scheduler_job" "campaign_scheduler" {
  depends_on = [google_project_service.required_apis]
  
  name        = "${local.resource_prefix}-campaign-scheduler"
  description = "Automated campaign execution scheduler"
  schedule    = "*/5 * * * *"  # Every 5 minutes
  time_zone   = "UTC"
  region      = var.region
  
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.web_service.uri}/api/v1/internal/check-scheduled-campaigns"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    oidc_token {
      service_account_email = google_service_account.scheduler_service_account.email
      audience             = google_cloud_run_v2_service.web_service.uri
    }
  }
  
  retry_config {
    retry_count          = 3
    max_retry_duration   = "300s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }
}

# Cleanup scheduler for old rate limits
resource "google_cloud_scheduler_job" "cleanup_scheduler" {
  depends_on = [google_project_service.required_apis]
  
  name        = "${local.resource_prefix}-cleanup-scheduler"
  description = "Cleanup old rate limit keys"
  schedule    = "0 */6 * * *"  # Every 6 hours
  time_zone   = "UTC"
  region      = var.region
  
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.web_service.uri}/api/v1/internal/cleanup-rate-limits"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    oidc_token {
      service_account_email = google_service_account.scheduler_service_account.email
      audience             = google_cloud_run_v2_service.web_service.uri
    }
  }
  
  retry_config {
    retry_count          = 2
    max_retry_duration   = "180s"
    min_backoff_duration = "5s"
    max_backoff_duration = "1800s"
    max_doublings        = 3
  }
}

# Database migration job (run once after deployment)
resource "google_cloud_scheduler_job" "migration_job" {
  depends_on = [google_project_service.required_apis]
  
  name        = "${local.resource_prefix}-migration-job"
  description = "Database migration job - run once after deployment"
  schedule    = "0 0 1 1 *"  # Run once on Jan 1st (effectively manual)
  time_zone   = "UTC"
  region      = var.region
  
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.web_service.uri}/api/v1/internal/migrate-database"
    
    headers = {
      "Content-Type" = "application/json"
    }
    
    oidc_token {
      service_account_email = google_service_account.scheduler_service_account.email
      audience             = google_cloud_run_v2_service.web_service.uri
    }
  }
  
  retry_config {
    retry_count = 1
  }
}