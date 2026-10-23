# ==============================================================================
# Modular IAM & Secret Manager Configuration (terraform/iam.tf)
# Provisions dedicated least-privilege service accounts (runtime + CI/CD deployer),
# scoped project-level IAM bindings, and Google Cloud Secret Manager secrets.
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. DEDICATED LEAST-PRIVILEGE SERVICE ACCOUNTS
# ------------------------------------------------------------------------------

resource "google_service_account" "agent_runtime" {
  account_id   = "scouts-bsa-agent-sa"
  display_name = "Scouts BSA Merit Badge Agent Runtime Service Account"
  description  = "Least-privilege service account for Cloud Run v2 multi-agent execution"
}

resource "google_service_account" "cicd_deployer" {
  account_id   = "scouts-bsa-cicd-deployer-sa"
  display_name = "Scouts BSA Canary CI/CD Deployer Service Account"
  description  = "Least-privilege service account for Cloud Build canary rollout and eval gating"
}

# ------------------------------------------------------------------------------
# 2. SCOPED RUNTIME IAM ROLE BINDINGS (LEAST PRIVILEGE)
# ------------------------------------------------------------------------------

resource "google_project_iam_member" "agent_vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_trace_writer" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_model_armor_user" {
  project = var.project_id
  role    = "roles/modelarmor.user"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_dlp_user" {
  project = var.project_id
  role    = "roles/dlp.user"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_project_iam_member" "agent_storage_object_user" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

# ------------------------------------------------------------------------------
# 3. CI/CD DEPLOYER IAM ROLE BINDINGS
# ------------------------------------------------------------------------------

resource "google_project_iam_member" "cicd_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cicd_deployer.email}"
}

resource "google_project_iam_member" "cicd_artifact_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.cicd_deployer.email}"
}

resource "google_service_account_iam_member" "cicd_act_as_runtime_sa" {
  service_account_id = google_service_account.agent_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.cicd_deployer.email}"
}

# ------------------------------------------------------------------------------
# 4. GOOGLE CLOUD SECRET MANAGER SECRETS
# ------------------------------------------------------------------------------

resource "google_secret_manager_secret" "bsa_api_key" {
  secret_id = "scouts-bsa-gemini-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "bsa_hitl_secret_key" {
  secret_id = "bsa-hitl-secret-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "admin_superuser_token" {
  secret_id = "admin-superuser-token"
  replication {
    auto {}
  }
}
