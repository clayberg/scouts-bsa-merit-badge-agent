variable "project_id" {
  description = "Google Cloud Project ID for deploying Scouts BSA Agent"
  type        = string
  default     = "clayberg-scouts-bsa-prod"
}

variable "region" {
  description = "Google Cloud Region for Cloud Run, VPC Subnet & Storage"
  type        = string
  default     = "us-central1"
}

variable "min_instances" {
  description = "Minimum warm Cloud Run instances to eliminate cold-start latency"
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Maximum Cloud Run horizontal autoscaling instances"
  type        = number
  default     = 10
}

variable "subnet_cidr" {
  description = "RFC 1918 CIDR range for the private Cloud Run egress subnet"
  type        = string
  default     = "10.24.0.0/24"
}
