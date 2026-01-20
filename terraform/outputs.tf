output "lambda_function_url" {
  description = "The public HTTPS endpoint for the Lambda function."
  value       = aws_lambda_function_url.main.function_url
}