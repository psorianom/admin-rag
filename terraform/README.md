# Terraform Deployment Guide

This directory contains Terraform configuration for deploying Admin-RAG to AWS Lambda + API Gateway.

## Prerequisites

- AWS account with credentials configured: `aws configure`
- Terraform installed: `terraform --version`
- Docker installed (for building Lambda image)

## Files Overview

| File | Purpose |
|------|---------|
| `provider.tf` | AWS provider configuration (region: eu-west-3) |
| `variables.tf` | Lambda settings (memory: 10GB, timeout: 30s, name) |
| `iam.tf` | IAM role and permissions for Lambda |
| `lambda.tf` | Lambda function + ECR repository |
| `api_gateway.tf` | Public HTTP endpoint for Lambda |
| `outputs.tf` | Display API URL, ECR URL, Lambda name |

## Deployment Steps

### Step 1: Initialize Terraform

Download AWS provider and set up working directory:

```bash
cd terraform
terraform init
```

**Output:** `Terraform has been successfully initialized!`

---

### Step 2: Validate Configuration

Check syntax of all `.tf` files:

```bash
terraform validate
```

**Output:** `Success! Configuration is valid.`

---

### Step 3: Plan Deployment

Preview what Terraform will create (DRY RUN):

```bash
terraform plan
```

**Output:** Shows all resources to be created:
- ECR repository
- Lambda function
- IAM role
- API Gateway
- Permissions

**Review this carefully before applying!**

---

### Step 4: Apply Deployment

Actually create the resources on AWS:

```bash
terraform apply
```

**Prompt:** `Do you want to perform these actions?` → Type `yes`

**Wait:** Takes ~2-3 minutes

**Output:** Shows:
```
Apply complete! Resources: 10 added, 0 changed, 0 destroyed.

Outputs:
api_endpoint = "https://abc123.execute-api.eu-west-3.amazonaws.com/prod"
ecr_repository_url = "908027388369.dkr.ecr.eu-west-3.amazonaws.com/admin-rag-retrieval"
lambda_function_name = "admin-rag-retrieval"
```

**Save these URLs!** You need the ECR URL for pushing Docker images.

---

### Step 5: Build Docker Image

Create Docker image locally:

```bash
cd ..  # Go back to project root
docker build -t admin-rag-retrieval .
```

---

### Step 6: Authenticate Docker to ECR

Get login credentials from AWS:

```bash
aws ecr get-login-password --region eu-west-3 | \
  docker login --username AWS --password-stdin <ECR_REPOSITORY_URL>
```

Replace `<ECR_REPOSITORY_URL>` with the URL from Step 4 output (e.g., `908027388369.dkr.ecr.eu-west-3.amazonaws.com`)

---

### Step 7: Push Docker Image to ECR

Upload your image:

```bash
docker push <ECR_REPOSITORY_URL>/admin-rag-retrieval:latest
```

**Wait:** Takes ~1-2 minutes (uploading 1GB image)

---

### Step 8: Test the API

Your Lambda is now live! Test it:

```bash
curl https://abc123.execute-api.eu-west-3.amazonaws.com/prod
```

(Use the `api_endpoint` from Step 4)

---

## Cleanup (Destroy Resources)

To delete everything and stop paying:

```bash
cd terraform
terraform destroy
```

**Prompt:** `Do you really want to destroy all resources?` → Type `yes`

**Wait:** Takes ~2-3 minutes

**Output:** `Destroy complete! Resources: 10 destroyed.`

---

## Troubleshooting

### Terraform init fails
- Check AWS credentials: `aws sts get-caller-identity`
- Check internet connection

### Terraform apply fails with permission error
- Check IAM user has permissions (Lambda, IAM, API Gateway, ECR, CloudWatch)

### Docker push fails with auth error
- Re-run ECR login: `aws ecr get-login-password ...`
- Credentials expire after ~12 hours

### Lambda shows "ResourceNotFoundException"
- Wait 1-2 minutes, ECR might still be processing image
- Check image was pushed: `aws ecr describe-images --repository-name admin-rag-retrieval`

---

## View Deployed Resources

List what was created:

```bash
terraform state list
```

Show details of a specific resource:

```bash
terraform state show aws_lambda_function.main
```

View all outputs again:

```bash
terraform output
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `terraform init` | Initialize workspace |
| `terraform validate` | Check syntax |
| `terraform plan` | Preview changes |
| `terraform apply` | Deploy to AWS |
| `terraform destroy` | Delete all resources |
| `terraform output` | Show outputs |
| `terraform state list` | List resources |
