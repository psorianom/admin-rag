# Configure Terraform and AWS provider settings

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Connect to AWS in Paris region (eu-west-3)
provider "aws" {
  region = "eu-west-3"
}

# Data sources for account info
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
