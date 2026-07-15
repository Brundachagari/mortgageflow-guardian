# Computed values reused across the other files.

locals {
  # e.g. "mortgageflow-guardian-dev" -- every resource name starts with this.
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "poc-ai-document-reliability"
  }
}
