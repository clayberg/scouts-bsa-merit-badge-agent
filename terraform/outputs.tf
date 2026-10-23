output "service_url" {
  description = "Primary URL of the deployed Scouts BSA Merit Badge Counselor Workbench on Cloud Run (us-central1)"
  value       = google_cloud_run_v2_service.workbench.uri
}

output "primary_cloud_run_url" {
  description = "Primary Cloud Run v2 service URI in var.region"
  value       = google_cloud_run_v2_service.workbench.uri
}

output "secondary_cloud_run_url" {
  description = "Secondary Cloud Run v2 replica URI in var.secondary_region (when enable_enterprise_ha = true)"
  value       = var.enable_enterprise_ha ? google_cloud_run_v2_service.workbench_secondary[0].uri : null
}

output "agent_runtime_service_account_email" {
  description = "Least-privilege runtime service account email for Cloud Run"
  value       = google_service_account.agent_runtime.email
}

output "cicd_deployer_service_account_email" {
  description = "Least-privilege CI/CD deployer service account email for Cloud Build"
  value       = google_service_account.cicd_deployer.email
}

output "secret_manager_secret_ids" {
  description = "Google Cloud Secret Manager secret identifiers wired into Cloud Run"
  value = {
    bsa_api_key           = google_secret_manager_secret.bsa_api_key.secret_id
    bsa_hitl_secret_key   = google_secret_manager_secret.bsa_hitl_secret_key.secret_id
    admin_superuser_token = google_secret_manager_secret.admin_superuser_token.secret_id
  }
}

output "storage_bucket" {
  description = "Cloud Storage bucket name for generated presentation decks"
  value       = google_storage_bucket.bsa_presentations.name
}

output "enterprise_ha_status" {
  description = "Summary of Phase 2 Enterprise HA, Cloud SQL pgvector, and VPC-SC Perimeter configuration"
  value = {
    enable_enterprise_ha    = var.enable_enterprise_ha
    enable_vpc_sc_perimeter = var.enable_vpc_sc_perimeter
    primary_region          = var.region
    secondary_region        = var.secondary_region
    memory_limit            = var.memory_limit
    render_max_concurrency  = var.render_max_concurrency
    cloudsql_instance_name  = var.enable_enterprise_ha ? google_sql_database_instance.pgvector_enterprise[0].name : "sqlite-wal-local-default"
  }
}
