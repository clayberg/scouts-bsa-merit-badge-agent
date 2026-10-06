# Terraform Infrastructure as Code for production Google Cloud deployment of Scouts BSA Agent.
# Provisions least-privilege IAM, custom VPC with Private Google Access, Cloud Armor WAF,
# Secret Manager, Cloud Storage, and Cloud Run v2 with health/readiness probes.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ==============================================================================
# 1. LEAST-PRIVILEGE SERVICE ACCOUNT & IAM BINDINGS
# ==============================================================================

resource "google_service_account" "scouts_agent_sa" {
  account_id   = "scouts-bsa-agent-sa"
  display_name = "Scouts BSA Merit Badge Agent Runtime Service Account"
  description  = "Least-privilege service account for Cloud Run multi-agent execution"
}

resource "google_project_iam_member" "agent_vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.scouts_agent_sa.email}"
}

resource "google_project_iam_member" "agent_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.scouts_agent_sa.email}"
}

resource "google_project_iam_member" "agent_storage_object_user" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.scouts_agent_sa.email}"
}

resource "google_project_iam_member" "agent_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.scouts_agent_sa.email}"
}

resource "google_project_iam_member" "agent_trace_writer" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.scouts_agent_sa.email}"
}

# ==============================================================================
# 2. VPC NETWORK SEGMENTATION, SUBNET & CLOUD ARMOR WAF POLICY
# ==============================================================================

resource "google_compute_network" "agent_vpc" {
  name                    = "scouts-bsa-agent-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "agent_subnet" {
  name                     = "scouts-bsa-agent-subnet"
  ip_cidr_range            = var.subnet_cidr
  region                   = var.region
  network                  = google_compute_network.agent_vpc.id
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_firewall" "allow_internal_and_hc" {
  name    = "scouts-bsa-allow-internal-and-gcp-hc"
  network = google_compute_network.agent_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["8085", "8501"]
  }

  # Google Cloud Load Balancer & Health Check ranges + private subnet
  source_ranges = ["35.191.0.0/16", "130.211.0.0/22", var.subnet_cidr]
  target_service_accounts = [
    google_service_account.scouts_agent_sa.email
  ]
}

resource "google_compute_security_policy" "agent_waf" {
  name        = "scouts-bsa-agent-cloud-armor-waf"
  description = "Cloud Armor WAF protecting Counselor Workbench against OWASP Top 10 and burst abuse"

  rule {
    action   = "deny(403)"
    priority = 1000
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('xss-stable') || evaluatePreconfiguredExpr('sqli-stable')"
      }
    }
    description = "Block SQLi and XSS payloads"
  }

  rule {
    action   = "throttle"
    priority = 2000
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 120
        interval_sec = 60
      }
    }
    description = "Per-IP rate limiting at 120 requests per minute"
  }

  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default allow rule behind WAF"
  }
}

# ==============================================================================
# 3. SECRET MANAGER & CLOUD STORAGE
# ==============================================================================

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "hitl_secret_key" {
  secret_id = "bsa-hitl-secret-key"
  replication {
    auto {}
  }
}

resource "google_storage_bucket" "bsa_presentations" {
  name                        = "${var.project_id}-bsa-presentations"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

# ==============================================================================
# 4. CLOUD RUN V2 SERVICE WITH DIRECT VPC EGRESS & HEALTH PROBES
# ==============================================================================

resource "google_cloud_run_v2_service" "scouts_bsa_agent_ui" {
  name     = "scouts-bsa-merit-badge-agent"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.scouts_agent_sa.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.agent_vpc.name
        subnetwork = google_compute_subnetwork.agent_subnet.name
      }
    }

    containers {
      image = "gcr.io/${var.project_id}/scouts-bsa-agent:latest"

      ports {
        container_port = 8085
      }

      resources {
        limits = {
          cpu    = "2000m"
          memory = "2Gi"
        }
      }

      startup_probe {
        http_get {
          path = "/readiness"
          port = 8085
        }
        initial_delay_seconds = 3
        period_seconds        = 5
        failure_threshold     = 6
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8085
        }
        period_seconds    = 15
        failure_threshold = 3
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "ENABLE_OPENTELEMETRY"
        value = "true"
      }
      env {
        name  = "USE_GCP_SECRET_MANAGER"
        value = "true"
      }
      env {
        name  = "AUTH_REQUIRED"
        value = "true"
      }
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "BSA_HITL_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.hitl_secret_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}
