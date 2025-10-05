# IAM Service Account and roles

resource "google_service_account" "app_service_account" {
  depends_on = [google_project_service.required_apis]
  
  account_id   = "${local.resource_prefix}-app-sa"
  display_name = "Event Stream Engine Application Service Account"
  description  = "Service account for Event Stream Engine Cloud Run services"
}

# Required IAM roles for the application
resource "google_project_iam_member" "app_roles" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/secretmanager.secretAccessor",
    "roles/redis.editor",
    "roles/run.invoker",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent"
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.app_service_account.email}"
}

# Allow Cloud Scheduler to invoke Cloud Run jobs
resource "google_service_account" "scheduler_service_account" {
  depends_on = [google_project_service.required_apis]
  
  account_id   = "${local.resource_prefix}-scheduler-sa"
  display_name = "Event Stream Engine Scheduler Service Account"
  description  = "Service account for Cloud Scheduler jobs"
}

resource "google_project_iam_member" "scheduler_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.scheduler_service_account.email}"
}

# Cloud Build service account for CI/CD (optional)
resource "google_service_account" "build_service_account" {
  depends_on = [google_project_service.required_apis]
  
  account_id   = "${local.resource_prefix}-build-sa"
  display_name = "Event Stream Engine Build Service Account"
  description  = "Service account for Cloud Build deployments"
}

resource "google_project_iam_member" "build_roles" {
  for_each = toset([
    "roles/run.developer",
    "roles/artifactregistry.writer",
    "roles/cloudbuild.builds.builder"
  ])
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.build_service_account.email}"
}