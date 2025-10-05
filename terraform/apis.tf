# Enable required GCP APIs

resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "redis.googleapis.com",
    "cloudscheduler.googleapis.com",
    "compute.googleapis.com",
    "vpcaccess.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudbuild.googleapis.com"
  ])
  
  service            = each.value
  disable_on_destroy = false
  
  timeouts {
    create = "10m"
    update = "10m"
  }
}