#!/bin/bash
# Script to clean up API Gateway resources from Terraform state

echo "=== Checking for API Gateway resources in Terraform state ==="
cd "$(dirname "$0")"

# List all API Gateway related resources
echo -e "\nAPI Gateway resources found:"
terraform state list | grep -E "(apigateway|api_gateway)" || echo "None found"

echo -e "\n=== Removing API Gateway resources from state ==="

# Remove API Gateway resources one by one
RESOURCES=$(terraform state list | grep -E "(apigateway|api_gateway)")

if [ -z "$RESOURCES" ]; then
    echo "No API Gateway resources to remove"
else
    for resource in $RESOURCES; do
        echo "Removing: $resource"
        terraform state rm "$resource"
    done
fi

echo -e "\n=== State cleanup complete ==="
echo -e "\nNext steps:"
echo "1. Review changes: terraform plan"
echo "2. Apply changes: terraform apply"
echo "3. Get Lambda Function URL: terraform output lambda_function_url"
