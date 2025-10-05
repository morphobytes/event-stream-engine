# Memorystore Redis instance for Celery broker and caching

resource "google_redis_instance" "redis_instance" {
  depends_on = [google_project_service.required_apis]
  
  name           = "${local.resource_prefix}-redis"
  tier           = "STANDARD_HA"  # High availability
  memory_size_gb = var.redis_memory_size_gb
  region         = var.region
  
  location_id             = var.zone
  alternative_location_id = "${substr(var.region, 0, length(var.region)-1)}b"
  
  authorized_network = google_compute_network.vpc_network.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  
  redis_version     = "REDIS_7_0"
  display_name      = "Event Stream Engine Redis Cache"
  reserved_ip_range = "10.1.0.0/29"
  
  redis_configs = {
    maxmemory-policy = "allkeys-lru"
    notify-keyspace-events = "Ex"
  }
  
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }
  
  persistence_config {
    persistence_mode = "RDB"
    rdb_snapshot_period = "TWENTY_FOUR_HOURS"
    rdb_snapshot_start_time = "02:00"
  }
  
  labels = local.common_labels
}