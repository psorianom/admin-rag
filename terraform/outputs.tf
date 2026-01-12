# Output values displayed after Terraform deployment
# These are printed to the terminal so you don't have to dig through AWS console

# Public API endpoint URL - used to call your Lambda function
output "api_endpoint" {
  description = "API Gateway public endpoint URL"
  value       = aws_apigatewayv2_stage.main.invoke_url
}

# ECR repository URL - used to push Docker images
output "ecr_repository_url" {
  description = "ECR repository URL for pushing Docker images"
  value       = aws_ecr_repository.lambda_repo.repository_url
}

# Lambda function name - reference for CloudWatch logs and debugging
output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.main.function_name
}
