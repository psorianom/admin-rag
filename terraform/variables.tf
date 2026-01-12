# Lambda function configuration variables

variable "function_name" {
  description = "Name of Lambda function"
  type        = string
  default     = "admin-rag-retrieval"
}

variable "lambda_memory" {
  description = "Lambda memory in MB (10GB = 10240)"
  type        = number
  default     = 3008  # 10GB for ONNX model + FastHTML
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds (cold start ~5s, queries ~0.06s)"
  type        = number
  default     = 30  # Buffer for cold starts
}
