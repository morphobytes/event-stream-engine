# Cloud SQL PostgreSQL instance

resource "google_sql_database_instance" "postgres_instance" {
  depends_on = [
    google_project_service.required_apis,
    google_service_networking_connection.private_vpc_connection
  ]
  
  name             = "${local.resource_prefix}-db"
  database_version = "POSTGRES_14"
  region           = var.region
  
  deletion_protection = var.enable_deletion_protection
  
  settings {
    tier              = var.db_instance_tier
    availability_type = "REGIONAL"  # HA configuration
    disk_type         = "PD_SSD"
    disk_size         = 20
    disk_autoresize   = true
    disk_autoresize_limit = 100
    
    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      location                       = var.region
      point_in_time_recovery_enabled = true
      
      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
      
      transaction_log_retention_days = 7
    }
    
    maintenance_window {
      day          = 7  # Sunday
      hour         = 3  # 3 AM
      update_track = "stable"
    }
    
    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.vpc_network.id
      enable_private_path_for_google_cloud_services = true
      
      authorized_networks {
        name  = "vpc-access-connector"
        value = "10.8.0.0/28"
      }
    }
    
    database_flags {
      name  = "log_statement"
      value = "all"
    }
    
    database_flags {
      name  = "log_min_duration_statement"
      value = "1000"  # Log queries longer than 1 second
    }
    
    database_flags {
      name  = "shared_preload_libraries"
      value = "pg_stat_statements"
    }
    
    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }
    
    user_labels = local.common_labels
  }
}

# Create application database
resource "google_sql_database" "app_database" {
  name     = "event_stream_prod"
  instance = google_sql_database_instance.postgres_instance.name
  
  deletion_policy = var.enable_deletion_protection ? "ABANDON" : "DELETE"
}

# Create database user
resource "google_sql_user" "app_user" {
  name     = "app_user"
  instance = google_sql_database_instance.postgres_instance.name
  password = random_password.db_password.result
  
  deletion_policy = var.enable_deletion_protection ? "ABANDON" : "DELETE"
}

# Create read-only user for analytics/reporting
resource "google_sql_user" "readonly_user" {
  name     = "readonly_user"
  instance = google_sql_database_instance.postgres_instance.name
  password = random_password.readonly_password.result
  
  deletion_policy = var.enable_deletion_protection ? "ABANDON" : "DELETE"
}

resource "random_password" "readonly_password" {
  length  = 32
  special = true
}