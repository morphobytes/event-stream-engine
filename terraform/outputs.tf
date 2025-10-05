# Terraform outputs for deployment information

output "web_service_url" {
  description = "URL of the deployed web service"
  value       = google_cloud_run_v2_service.web_service.uri
}

output "database_connection_name" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.postgres_instance.connection_name
}

output "database_private_ip" {
  description = "Private IP address of the database"
  value       = google_sql_database_instance.postgres_instance.private_ip_address
  sensitive   = true
}

output "redis_host" {
  description = "Redis instance host"
  value       = google_redis_instance.redis_instance.host
  sensitive   = true
}

output "redis_port" {
  description = "Redis instance port"
  value       = google_redis_instance.redis_instance.port
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.container_registry.repository_id}"
}

output "service_account_email" {
  description = "Application service account email"
  value       = google_service_account.app_service_account.email
}

output "twilio_webhook_urls" {
  description = "URLs to configure in Twilio console"
  value = {
    inbound_webhook = "${google_cloud_run_v2_service.web_service.uri}/webhooks/inbound"
    status_webhook  = "${google_cloud_run_v2_service.web_service.uri}/webhooks/status"
  }
}

output "database_credentials" {
  description = "Database connection information"
  value = {
    host     = google_sql_database_instance.postgres_instance.private_ip_address
    database = google_sql_database.app_database.name
    username = google_sql_user.app_user.name
  }
  sensitive = true
}

output "vpc_network_name" {
  description = "VPC network name"
  value       = google_compute_network.vpc_network.name
}

output "vpc_connector_name" {
  description = "VPC Access Connector name"
  value       = google_vpc_access_connector.serverless_connector.name
}

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "deployment_summary" {
  description = "Complete deployment summary"
  value = {
    web_service_url     = google_cloud_run_v2_service.web_service.uri
    inbound_webhook_url = "${google_cloud_run_v2_service.web_service.uri}/webhooks/inbound"
    status_webhook_url  = "${google_cloud_run_v2_service.web_service.uri}/webhooks/status"
    health_check_url    = "${google_cloud_run_v2_service.web_service.uri}/health"
    api_docs_url        = "${google_cloud_run_v2_service.web_service.uri}/api/v1/docs"
    artifact_registry   = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.container_registry.repository_id}"
    project_id          = var.project_id
    region              = var.region
    environment         = var.environment
  }
}