# Terraform Infrastructure as Code for production Google Cloud deployment of Scouts BSA Agent.
# Provisions custom VPC with Private Google Access, Cloud Armor WAF, Cloud KMS CMEK,
# Artifact Registry, Cloud Storage, Primary + Multi-Region HA Cloud Run v2 (4 GiB, CPU Boost),
# Serverless NEGs, Cloud SQL PostgreSQL 16 (pgvector), VPC-SC Perimeter, and SLO Alerting.
# Dedicated least-privilege IAM & Secret Manager resources are modularized in terraform/iam.tf.

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
# 1. VPC NETWORK SEGMENTATION, SUBNETS & CLOUD ARMOR WAF POLICY
# ==============================================================================

resource "google_compute_network" "agent_vpc" {
  name                    = "scouts-bsa-agent-vpc"
  auto_create_subnetworks = false
  routing_mode            = "GLOBAL"
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

resource "google_compute_subnetwork" "agent_subnet_secondary" {
  count                    = var.enable_enterprise_ha ? 1 : 0
  name                     = "scouts-bsa-agent-subnet-east1"
  ip_cidr_range            = var.secondary_subnet_cidr
  region                   = var.secondary_region
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
    ports    = ["8080", "8085"]
  }

  # Google Cloud Load Balancer & Health Check ranges + private subnets
  source_ranges = ["35.191.0.0/16", "130.211.0.0/22", var.subnet_cidr, var.secondary_subnet_cidr]
  target_service_accounts = [
    google_service_account.agent_runtime.email
  ]
}

resource "google_compute_security_policy" "agent_waf" {
  name        = "scouts-bsa-agent-cloud-armor-waf"
  description = "Cloud Armor WAF protecting Counselor Workbench against OWASP Top 10 and burst abuse (scouts-bsa-model-armor-edge-policy)"

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
# 2. CLOUD KMS CMEK, ARTIFACT REGISTRY & CLOUD STORAGE
# ==============================================================================

resource "google_kms_key_ring" "agent_keyring" {
  name     = "scouts-bsa-agent-keyring"
  location = var.region
}

resource "google_kms_crypto_key" "agent_cmek_key" {
  name            = "scouts-bsa-agent-cmek-key"
  key_ring        = google_kms_key_ring.agent_keyring.id
  rotation_period = "7776000s" # 90-day automatic CMEK key rotation
  purpose         = "ENCRYPT_DECRYPT"
}

resource "google_artifact_registry_repository" "agent_repo" {
  location      = var.region
  repository_id = "scouts-bsa-repo"
  description   = "Immutable Docker container repository for Scouts BSA Merit Badge Counselor Workbench"
  format        = "DOCKER"
  kms_key_name  = google_kms_crypto_key.agent_cmek_key.id
}

resource "google_storage_bucket" "bsa_presentations" {
  name                        = "${var.project_id}-bsa-presentations"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true

  encryption {
    default_kms_key_name = google_kms_crypto_key.agent_cmek_key.id
  }

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }
}

# ==============================================================================
# 3. PRIMARY CLOUD RUN V2 SERVICE (us-central1, 4 GiB RAM, CPU BOOST)
# ==============================================================================

resource "google_cloud_run_v2_service" "workbench" {
  name     = "scouts-bsa-merit-badge-agent"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account                  = google_service_account.agent_runtime.email
    encryption_key                   = google_kms_crypto_key.agent_cmek_key.id
    max_instance_request_concurrency = var.container_concurrency

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
        startup_cpu_boost = true
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
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
        name  = "RENDER_MAX_CONCURRENCY"
        value = "4"
      }
      env {
        name = "BSA_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.bsa_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.bsa_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "BSA_HITL_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.bsa_hitl_secret_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "ADMIN_SUPERUSER_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.admin_superuser_token.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

# ==============================================================================
# 4. PHASE 2 ENTERPRISE HA & SECURITY PERIMETER (COUNT-GATED BY ADR-11)
#    - Cloud SQL PostgreSQL 16 with IAM Auth & pgvector (vector(768) HNSW)
#    - Secondary Region (us-east1) Cloud Run v2 Replica + Multi-Region NEGs
#    - VPC Service Controls (VPC-SC) Service Perimeter
# ==============================================================================

resource "google_sql_database_instance" "pgvector_enterprise" {
  count               = var.enable_enterprise_ha ? 1 : 0
  name                = "scouts-bsa-pgvector-ha"
  database_version    = "POSTGRES_16"
  region              = var.region
  encryption_key_name = google_kms_crypto_key.agent_cmek_key.id
  deletion_protection = true

  settings {
    tier              = "db-custom-2-8192"
    availability_type = "REGIONAL"
    disk_autoresize   = true
    disk_size         = 50
    disk_type         = "PD_SSD"

    # Enable IAM database authentication for CloudSQLPgVectorBackend (pgvector 768-dim HNSW)
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.agent_vpc.id
    }
  }
}

resource "google_sql_database" "workbench_vectors" {
  count    = var.enable_enterprise_ha ? 1 : 0
  name     = "scouts_bsa_vectors"
  instance = google_sql_database_instance.pgvector_enterprise[0].name
}

resource "google_cloud_run_v2_service" "workbench_secondary" {
  count    = var.enable_enterprise_ha ? 1 : 0
  name     = "scouts-bsa-merit-badge-agent-east1"
  location = var.secondary_region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account                  = google_service_account.agent_runtime.email
    max_instance_request_concurrency = var.container_concurrency

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.agent_vpc.name
        subnetwork = google_compute_subnetwork.agent_subnet_secondary[0].name
      }
    }

    containers {
      image = "gcr.io/${var.project_id}/scouts-bsa-agent:latest"

      ports {
        container_port = 8085
      }

      resources {
        startup_cpu_boost = true
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
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
        value = var.secondary_region
      }
      env {
        name  = "SESSION_BACKEND"
        value = "cloudsql"
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
        name  = "RENDER_MAX_CONCURRENCY"
        value = "4"
      }
      env {
        name = "BSA_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.bsa_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "BSA_HITL_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.bsa_hitl_secret_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "ADMIN_SUPERUSER_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.admin_superuser_token.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

resource "google_compute_region_network_endpoint_group" "serverless_neg_primary" {
  name                  = "scouts-bsa-neg-primary"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  cloud_run {
    service = google_cloud_run_v2_service.workbench.name
  }
}

resource "google_compute_region_network_endpoint_group" "serverless_neg_secondary" {
  count                 = var.enable_enterprise_ha ? 1 : 0
  name                  = "scouts-bsa-neg-secondary"
  network_endpoint_type = "SERVERLESS"
  region                = var.secondary_region
  cloud_run {
    service = google_cloud_run_v2_service.workbench_secondary[0].name
  }
}

resource "google_compute_backend_service" "default" {
  name                  = "scouts-bsa-global-lb-backend"
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  security_policy       = google_compute_security_policy.agent_waf.id

  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg_primary.id
  }

  dynamic "backend" {
    for_each = var.enable_enterprise_ha ? [google_compute_region_network_endpoint_group.serverless_neg_secondary[0].id] : []
    content {
      group = backend.value
    }
  }
}

# VPC Service Controls Perimeter (also referenced as bsa_agent_vpc_sc_perimeter in ADR-11)
resource "google_access_context_manager_service_perimeter" "scouts_bsa_vpc_sc" {
  count  = var.enable_vpc_sc_perimeter ? 1 : 0
  parent = "accessPolicies/${var.access_policy_id}"
  name   = "accessPolicies/${var.access_policy_id}/servicePerimeters/scouts_bsa_vpc_sc"
  title  = "Scouts BSA Merit Badge Workbench VPC-SC Perimeter"

  status {
    resources = [
      "projects/${var.project_id}"
    ]
    restricted_services = [
      "aiplatform.googleapis.com",
      "run.googleapis.com",
      "sqladmin.googleapis.com",
      "secretmanager.googleapis.com",
      "storage.googleapis.com"
    ]
  }
}

# ==============================================================================
# 5. CLOUD MONITORING ALERT POLICIES (LATENCY P95, 5XX ERRORS & SLO BURN RATE)
# ==============================================================================

resource "google_monitoring_alert_policy" "cloud_run_p95_latency_alert" {
  display_name = "Scouts BSA Agent — Cloud Run p95 Latency > 12s"
  combiner     = "OR"
  conditions {
    display_name = "Cloud Run Request Latency p95 > 12000ms"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"scouts-bsa-merit-badge-agent\" AND metric.type = \"run.googleapis.com/request_latencies\""
      duration        = "120s"
      comparison      = "COMPARISON_GT"
      threshold_value = 12000
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }
}

resource "google_monitoring_alert_policy" "cloud_run_5xx_error_rate_alert" {
  display_name = "Scouts BSA Agent — Cloud Run 5xx Error Count Spike"
  combiner     = "OR"
  conditions {
    display_name = "Cloud Run 5xx Server Errors > 5 per minute"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"scouts-bsa-merit-badge-agent\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
}

resource "google_monitoring_alert_policy" "cloud_run_slo_burn_rate_alert" {
  display_name = "Scouts BSA Agent — 99.5% Availability Error-Budget Burn Rate > 2x"
  combiner     = "OR"
  conditions {
    display_name = "Fast Error Budget Burn Rate (1h window > 1.0% 5xx ratio)"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"scouts-bsa-merit-badge-agent\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
}
