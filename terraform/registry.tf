# Artifact Registry for container images

resource "google_artifact_registry_repository" "container_registry" {
  depends_on = [google_project_service.required_apis]
  
  location      = var.region
  repository_id = "${local.resource_prefix}-containers"
  description   = "Container registry for Event Stream Engine"
  format        = "DOCKER"
  
  labels = local.common_labels
  
  cleanup_policies {
    id     = "keep-latest-versions"
    action = "KEEP"
    
    most_recent_versions {
      keep_count = 10
    }
  }
  
  cleanup_policies {
    id     = "delete-old-versions"
    action = "DELETE"
    
    condition {
      older_than = "2592000s"  # 30 days
    }
  }
}

# IAM binding to allow Cloud Run to pull images
resource "google_artifact_registry_repository_iam_member" "cloud_run_pull" {
  location   = google_artifact_registry_repository.container_registry.location
  repository = google_artifact_registry_repository.container_registry.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.app_service_account.email}"
}

# IAM binding to allow Cloud Build to push images
resource "google_artifact_registry_repository_iam_member" "cloud_build_push" {
  location   = google_artifact_registry_repository.container_registry.location
  repository = google_artifact_registry_repository.container_registry.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.build_service_account.email}"
}