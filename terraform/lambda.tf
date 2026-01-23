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
    }
  }
}

# Lambda Function URL requires TWO permissions for auth_type="NONE"
# See: https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html
resource "aws_lambda_permission" "function_url_invoke_url" {
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.main.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "function_url_invoke_function" {
  statement_id  = "FunctionURLInvokeFunction"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "*"
}

# Create Lambda Function URL for public access
# This replaces API Gateway and allows Lambda's full timeout (120s) to be used
resource "aws_lambda_function_url" "main" {
  function_name      = aws_lambda_function.main.function_name
  authorization_type = "NONE"  # Public access without authentication

  depends_on = [
    aws_lambda_permission.function_url_invoke_url,
    aws_lambda_permission.function_url_invoke_function
  ]

  cors {
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST", "PUT", "DELETE"]
    allow_headers     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}

