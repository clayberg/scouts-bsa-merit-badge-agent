output "service_url" {
  description = "URL of the deployed Scouts BSA Agent Streamlit UI on Cloud Run"
  value       = google_cloud_run_v2_service.scouts_bsa_agent_ui.uri
}

output "storage_bucket" {
  description = "Cloud Storage bucket name for generated presentation decks"
  value       = google_storage_bucket.bsa_presentations.name
}
