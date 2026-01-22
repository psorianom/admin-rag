# Terraform Infrastructure

This directory contains the Terraform configuration for deploying the Admin-RAG application on AWS.

## Architecture: Lambda Function URL

The infrastructure is designed to be simple, robust, and cost-effective (serverless). It consists of the following main components:

1.  **Amazon ECR (Elastic Container Registry)**:
    *   A private Docker registry to store the application's container image.
    *   Defined in `lambda.tf`.

2.  **AWS Lambda Function**:
    *   The core compute component that runs the application container.
    *   It is configured with 3GB of memory and a **120-second timeout** to handle the long cold start caused by the initial model loading (~90 seconds).
    *   Defined in `lambda.tf`.

3.  **Lambda Function URL**:
    *   This provides a dedicated, public HTTPS endpoint directly for the Lambda function.
    *   This architecture was chosen specifically to bypass the **29-second timeout limit** of API Gateway, which was preventing the UI from receiving a response during a cold start.
    *   The Function URL's timeout is linked to the Lambda function's timeout, solving the primary deployment issue.
    *   Defined in `lambda.tf`.

4.  **IAM Role**:
    *   An IAM role that grants the Lambda function the necessary permissions to run and write logs to CloudWatch.
    *   Defined in `iam.tf`.

### Deployment Flow

The request flow is very direct:

```
User's Browser -> Lambda Function URL -> AWS Lambda -> Application Container
```

### How to Deploy

The `Makefile` in the root directory automates the entire deployment process.

```bash
# From the project root
make deploy
```

This command will:
1.  Build the Docker image.
2.  Push the image to the ECR repository.
3.  Run `terraform apply` to provision or update the AWS resources.

### Outputs

After deployment, the public URL of the application will be displayed as a Terraform output. You can also retrieve it at any time by running:

```bash
cd terraform
terraform output lambda_function_url
```