# API Gateway configuration - creates public HTTP endpoint for Lambda

# Block 1: Create the HTTP API Gateway
# This is the public entry point for your Lambda function
resource "aws_apigatewayv2_api" "main" {
  name          = "${var.function_name}-api"
  protocol_type = "HTTP"  # Use HTTP (not HTTPS for simplicity)
}

# Block 2: Create integration between API Gateway and Lambda
# This tells API Gateway: "when you get a request, send it to this Lambda function"
resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "AWS_PROXY"  # Lambda returns full HTTP response
  integration_uri  = aws_lambda_function.main.invoke_arn
}

# Block 3: Create route - the URL pattern matcher
# "$default" = catch ALL requests (any path, any HTTP method)
# When a request matches, route it to the integration (Block 2)
resource "aws_apigatewayv2_route" "main" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "$default"  # Match all requests
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Block 4: Create deployment stage
# This deploys the API live and creates the public URL
resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "prod"  # Stage name (appears in URL)
  auto_deploy = true   # Automatically deploy when API changes
}

# Block 5: Grant permission for API Gateway to invoke Lambda
# CRITICAL: Without this, API Gateway cannot call Lambda (permission denied)
# This is the security rule that connects everything
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "apigateway.amazonaws.com"  # Allow API Gateway service
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# FLOW SUMMARY:
# User Request
#   ↓
# Block 1: Hits public API (created by API Gateway)
#   ↓
# Block 3: Route matcher checks "$default" - matches all requests
#   ↓
# Block 2: Integration sends request to Lambda
#   ↓
# Block 5: Permission check - allows API Gateway to invoke Lambda
#   ↓
# Lambda function executes
#   ↓
# Block 4: Stage "prod" returns response to user
