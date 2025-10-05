# Cloud Run services for web application and worker

# Web/API Service
resource "google_cloud_run_v2_service" "web_service" {
  depends_on = [
    google_project_service.required_apis,
    google_sql_database_instance.postgres_instance,
    google_redis_instance.redis_instance
  ]
  
  name     = "${local.resource_prefix}-web"
  location = var.region
  
  template {
    service_account = google_service_account.app_service_account.email
    
    vpc_access {
      connector = google_vpc_access_connector.serverless_connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }
    
    containers {
      image = var.container_image
      
      ports {
        name           = "http1"
        container_port = 8000
      }
      
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
        
        cpu_idle = true
        startup_cpu_boost = true
      }
      
      # Environment variables
      env {
        name  = "DATABASE_URL"
        value = "postgresql://${google_sql_user.app_user.name}:${random_password.db_password.result}@${google_sql_database_instance.postgres_instance.private_ip_address}:5432/${google_sql_database.app_database.name}"
      }
      
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.redis_instance.host}:${google_redis_instance.redis_instance.port}/0"
      }
      
      env {
        name  = "CELERY_BROKER_URL"
        value = "redis://${google_redis_instance.redis_instance.host}:${google_redis_instance.redis_instance.port}/0"
      }
      
      env {
        name  = "CELERY_RESULT_BACKEND"
        value = "redis://${google_redis_instance.redis_instance.host}:${google_redis_instance.redis_instance.port}/0"
      }
      
      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.flask_secret_key.secret_id
            version = "latest"
          }
        }
      }
      
      env {
        name = "TWILIO_ACCOUNT_SID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.twilio_account_sid.secret_id
            version = "latest"
          }
        }
      }
      
      env {
        name = "TWILIO_AUTH_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.twilio_auth_token.secret_id
            version = "latest"
          }
        }
      }
      
      env {
        name  = "TWILIO_PHONE_NUMBER"
        value = var.twilio_phone_number
      }
      
      env {
        name  = "FLASK_ENV"
        value = "production"
      }
      
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      
      # Health check configuration
      startup_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 10
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 3
      }
      
      liveness_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 30
        timeout_seconds       = 5
        period_seconds        = 30
        failure_threshold     = 3
      }
    }
    
    scaling {
      min_instance_count = var.min_web_instances
      max_instance_count = var.max_web_instances
    }
    
    max_instance_request_concurrency = 100
    timeout                         = "300s"
  }
  
  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
  
  labels = local.common_labels
}

# Campaign Worker Job
resource "google_cloud_run_v2_job" "worker_job" {
  depends_on = [
    google_project_service.required_apis,
    google_sql_database_instance.postgres_instance,
    google_redis_instance.redis_instance
  ]
  
  name     = "${local.resource_prefix}-worker"
  location = var.region
  
  template {
    template {
      service_account = google_service_account.app_service_account.email
      
      vpc_access {
        connector = google_vpc_access_connector.serverless_connector.id
        egress    = "PRIVATE_RANGES_ONLY"
      }
      
      containers {
        image = var.container_image
        
        command = ["celery"]
        args    = ["-A", "app.main:celery_app", "worker", "--loglevel=info", "--pool=solo"]
        
        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }
        
        # Environment variables (same as web service)
        env {
          name  = "DATABASE_URL"
          value = "postgresql://${google_sql_user.app_user.name}:${random_password.db_password.result}@${google_sql_database_instance.postgres_instance.private_ip_address}:5432/${google_sql_database.app_database.name}"
        }
        
        env {
          name  = "REDIS_URL"
          value = "redis://${google_redis_instance.redis_instance.host}:${google_redis_instance.redis_instance.port}/0"
        }
        
        env {
          name  = "CELERY_BROKER_URL"
          value = "redis://${google_redis_instance.redis_instance.host}:${google_redis_instance.redis_instance.port}/0"
        }
        
        env {
          name  = "CELERY_RESULT_BACKEND"
          value = "redis://${google_redis_instance.redis_instance.host}:${google_redis_instance.redis_instance.port}/0"
        }
        
        env {
          name = "SECRET_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.flask_secret_key.secret_id
              version = "latest"
            }
          }
        }
        
        env {
          name = "TWILIO_ACCOUNT_SID"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.twilio_account_sid.secret_id
              version = "latest"
            }
          }
        }
        
        env {
          name = "TWILIO_AUTH_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.twilio_auth_token.secret_id
              version = "latest"
            }
          }
        }
        
        env {
          name  = "TWILIO_PHONE_NUMBER"
          value = var.twilio_phone_number
        }
        
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
      }
      
      task_count    = 1
      parallelism   = 1
      task_timeout  = "3600s"  # 1 hour timeout
      
      max_retries = 3
    }
  }
  
  labels = local.common_labels
}

# Allow unauthenticated access to web service (for Twilio webhooks)
resource "google_cloud_run_v2_service_iam_member" "web_public_access" {
  location = google_cloud_run_v2_service.web_service.location
  name     = google_cloud_run_v2_service.web_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}