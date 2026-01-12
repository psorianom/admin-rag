output "api_endpoint" {                                                                                            
  description = "API Gateway public endpoint URL"                                                                  
  value       = aws_apigatewayv2_stage.main.invoke_url                                                             
}                                                                                                                  
                                                                                                                    
output "ecr_repository_url" {                                                                                      
  description = "ECR repository URL for pushing Docker images"                                                     
  value       = aws_ecr_repository.lambda_repo.repository_url                                                      
}                                                                                                                  
                                                                                                                    
output "lambda_function_name" {                                                                                    
  description = "Lambda function name"                                                                             
  value       = aws_lambda_function.main.function_name                                                             
} 