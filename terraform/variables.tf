variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-southeast-1"
}

variable "replica_region" {
  description = "Secondary AWS region for S3 cross-region replication (Phase 14)."
  type        = string
  default     = "ap-southeast-3"  # Jakarta — geo-redundancy for ap-southeast-1
}

variable "project_name" {
  description = "Project name used to prefix all resources."
  type        = string
  default     = "spm"
}

variable "environment" {
  description = "Environment name (staging, production)."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be 'staging' or 'production'."
  }
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "spm-cluster"
}

variable "domain_name" {
  description = "Public domain for the app (used for the TLS cert)."
  type        = string
  default     = "spm.example.com"
}

variable "db_password" {
  description = "Master password for the RDS Postgres instance."
  type        = string
  sensitive   = true
}

variable "redis_auth_token" {
  description = "AUTH token for ElastiCache Redis (transit encryption)."
  type        = string
  sensitive   = true
}
