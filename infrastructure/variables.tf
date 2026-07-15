# Inputs you can tune without editing the resource files.
# Override any of these at deploy time with -var, or in a terraform.tfvars file.

variable "project_name" {
  description = "Short name used as a prefix for every resource."
  type        = string
  default     = "mortgageflow-guardian"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "reviewer_email" {
  description = "Email that receives human-review SNS alerts. Empty = no email subscription created."
  type        = string
  default     = ""
}

variable "lambda_runtime" {
  description = "Python runtime for the Lambda functions."
  type        = string
  default     = "python3.12"
}

variable "allowed_extensions" {
  description = "Comma-separated file extensions the ingestion Lambda accepts."
  type        = string
  default     = "pdf,png,jpg,jpeg,json"
}

variable "max_file_mb" {
  description = "Maximum accepted upload size, in megabytes."
  type        = number
  default     = 10
}

variable "log_retention_days" {
  description = "How long to keep CloudWatch logs. Keeps storage cost predictable."
  type        = number
  default     = 14
}
