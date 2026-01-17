# Lambda function and container registry

# Create ECR repository for Lambda Docker image
resource "aws_ecr_repository" "lambda_repo" {
  name                 = var.function_name
  image_tag_mutability = "MUTABLE"  # Allow overwriting image tags during deployment
}

data "aws_ecr_image" "lambda_image" {
  repository_name = aws_ecr_repository.lambda_repo.name
  image_tag       = "latest" # We want to get the digest of the image tagged 'latest'
}

# Create Lambda function with Docker image
resource "aws_lambda_function" "main" {
  function_name = var.function_name
  role          = aws_iam_role.lambda_role.arn  # Use the IAM role from iam.tf
  memory_size   = var.lambda_memory             # 10GB for ONNX model
  timeout       = var.lambda_timeout            # 30 seconds timeout

  package_type = "Image"  # Use Docker image instead of zip
  image_uri    = "${aws_ecr_repository.lambda_repo.repository_url}@${data.aws_ecr_image.lambda_image.image_digest}"  # Pull image from ECR using digest

  environment {
    variables = {
      QDRANT_TYPE            = var.qdrant_type
      QDRANT_CLOUD_URL       = var.qdrant_cloud_url
      QDRANT_CLOUD_API_KEY   = var.qdrant_cloud_api_key
      LLM_PROVIDER           = var.llm_provider
      OPENAI_API_KEY         = var.openai_api_key
      OPENAI_MODEL           = var.openai_model
      API_STAGE              = "prod"  # Pass API Gateway stage to app
    }
  }
}
