# VPC and networking configuration

resource "google_compute_network" "vpc_network" {
  depends_on = [google_project_service.required_apis]
  
  name                    = "${local.resource_prefix}-vpc"
  auto_create_subnetworks = false
  description             = "VPC network for Event Stream Engine"
  
  delete_default_routes_on_create = false
}

resource "google_compute_subnetwork" "private_subnet" {
  name          = "${local.resource_prefix}-private-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc_network.id
  
  description = "Private subnet for Event Stream Engine services"
  
  private_ip_google_access = true
}

# VPC Access Connector for serverless services
resource "google_vpc_access_connector" "serverless_connector" {
  depends_on = [google_project_service.required_apis]
  
  name          = "${local.resource_prefix}-connector"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.vpc_network.name
  
  min_instances = 2
  max_instances = 3
  
  machine_type = "e2-micro"
}

# Private service connection for Cloud SQL
resource "google_compute_global_address" "private_ip_address" {
  depends_on = [google_project_service.required_apis]
  
  name          = "${local.resource_prefix}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc_network.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  depends_on = [google_project_service.required_apis]
  
  network                 = google_compute_network.vpc_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

# Firewall rules for health checks
resource "google_compute_firewall" "allow_health_checks" {
  name    = "${local.resource_prefix}-allow-health-checks"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["8000", "8080"]
  }

  source_ranges = [
    "130.211.0.0/22",  # Google health check ranges
    "35.191.0.0/16"
  ]

  target_tags = ["event-stream-service"]
}