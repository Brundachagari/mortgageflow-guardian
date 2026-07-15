# Provider + Terraform settings.
#
# This block pins the tools and the cloud provider. It is written to be
# compatible with BOTH Terraform and OpenTofu (the open-source fork) -- the
# syntax is identical, so `tofu` can run these files unchanged.

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # Every resource automatically gets these tags -- useful for cost tracking
  # and for knowing "what created this?" in a shared account.
  default_tags {
    tags = local.common_tags
  }
}

# Who am I? Used to build a globally-unique S3 bucket name from the account id.
data "aws_caller_identity" "current" {}
