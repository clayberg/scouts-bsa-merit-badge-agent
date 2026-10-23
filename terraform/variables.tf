variable "project_id" {
  description = "Google Cloud Project ID for deploying Scouts BSA Agent"
  type        = string
  default     = "clayberg-scouts-bsa-prod"
}

variable "region" {
  description = "Primary Google Cloud Region for Cloud Run, VPC Subnet & Storage"
  type        = string
  default     = "us-central1"
}

variable "secondary_region" {
  description = "Secondary Google Cloud Region for multi-region HA Cloud Run & Serverless NEG"
  type        = string
  default     = "us-east1"
}

variable "environment" {
  description = "Deployment environment label (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "cpu_limit" {
  description = "Cloud Run container CPU allocation (2 vCPU with startup CPU boost)"
  type        = string
  default     = "2000m"
}

variable "memory_limit" {
  description = "Cloud Run container memory limit matching Slide 12 (4 GiB, CPU Boost)"
  type        = string
  default     = "4Gi"
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

variable "container_concurrency" {
  description = "Maximum concurrent requests per Cloud Run container instance"
  type        = number
  default     = 80
}

variable "render_max_concurrency" {
  description = "Bounded semaphore cap for concurrent python-pptx/PIL synthesis per instance"
  type        = string
  default     = "4"
}

variable "subnet_cidr" {
  description = "RFC 1918 CIDR range for the primary private Cloud Run egress subnet"
  type        = string
  default     = "10.24.0.0/24"
}

variable "secondary_subnet_cidr" {
  description = "RFC 1918 CIDR range for the secondary region private Cloud Run egress subnet"
  type        = string
  default     = "10.25.0.0/24"
}

variable "enable_enterprise_ha" {
  description = "Enable Phase 2 Enterprise HA resources (Cloud SQL pgvector POSTGRES_16 + us-east1 Cloud Run replica & Serverless NEG)"
  type        = bool
  default     = false
}

variable "enable_vpc_sc_perimeter" {
  description = "Enable Organization-level VPC Service Controls (VPC-SC) perimeter around AI Platform, Cloud Run, Cloud SQL, Secret Manager, and GCS"
  type        = bool
  default     = false
}

variable "access_policy_id" {
  description = "Google Cloud Organization Access Context Manager Policy ID when enable_vpc_sc_perimeter is true"
  type        = string
  default     = "000000000000"
}
