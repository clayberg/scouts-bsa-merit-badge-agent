variable "project_id" {
  description = "Google Cloud Project ID for deploying Scouts BSA Agent"
  type        = string
  default     = "clayberg-scouts-bsa-prod"
}

variable "region" {
  description = "Google Cloud Region for Cloud Run & Storage"
  type        = string
  default     = "us-central1"
}
