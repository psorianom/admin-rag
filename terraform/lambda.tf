# Lambda function and container registry

# Create ECR repository for Lambda Docker image
resource "aws_ecr_repository" "lambda_repo" {
  name                 = var.function_name
  image_tag_mutability = "MUTABLE"  # Allow overwriting image tags during deployment
}

# Create Lambda function with Docker image
resource "aws_lambda_function" "main" {
  function_name = var.function_name
  role          = aws_iam_role.lambda_role.arn  # Use the IAM role from iam.tf
  memory_size   = var.lambda_memory             # 10GB for ONNX model
  timeout       = var.lambda_timeout            # 30 seconds timeout

  package_type = "Image"  # Use Docker image instead of zip
  image_uri    = "${aws_ecr_repository.lambda_repo.repository_url}:latest"  # Pull image from ECR
}
