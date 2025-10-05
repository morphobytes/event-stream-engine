# Secret Manager configuration

# Generate random passwords
resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "random_password" "flask_secret_key" {
  length  = 64
  special = true
}

# Database password secret
resource "google_secret_manager_secret" "db_password" {
  depends_on = [google_project_service.required_apis]
  
  secret_id = "${local.resource_prefix}-db-password"
  
  labels = local.common_labels
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

# Flask secret key
resource "google_secret_manager_secret" "flask_secret_key" {
  depends_on = [google_project_service.required_apis]
  
  secret_id = "${local.resource_prefix}-flask-secret-key"
  labels    = local.common_labels
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "flask_secret_key" {
  secret = google_secret_manager_secret.flask_secret_key.id
  secret_data = random_password.flask_secret_key.result
}

# Twilio Account SID secret
resource "google_secret_manager_secret" "twilio_account_sid" {
  depends_on = [google_project_service.required_apis]
  
  secret_id = "${local.resource_prefix}-twilio-account-sid"
  labels    = local.common_labels
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "twilio_account_sid" {
  count = var.twilio_account_sid != "" ? 1 : 0
  
  secret = google_secret_manager_secret.twilio_account_sid.id
  secret_data = var.twilio_account_sid
}

# Twilio Auth Token secret
resource "google_secret_manager_secret" "twilio_auth_token" {
  depends_on = [google_project_service.required_apis]
  
  secret_id = "${local.resource_prefix}-twilio-auth-token"
  labels    = local.common_labels
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "twilio_auth_token" {
  count = var.twilio_auth_token != "" ? 1 : 0
  
  secret = google_secret_manager_secret.twilio_auth_token.id
  secret_data = var.twilio_auth_token
}

# IAM bindings for secret access
resource "google_secret_manager_secret_iam_member" "app_secret_access" {
  for_each = toset([
    google_secret_manager_secret.db_password.secret_id,
    google_secret_manager_secret.flask_secret_key.secret_id,
    google_secret_manager_secret.twilio_account_sid.secret_id,
    google_secret_manager_secret.twilio_auth_token.secret_id
  ])
  
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app_service_account.email}"
}