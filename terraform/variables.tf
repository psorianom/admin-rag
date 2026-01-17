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
  default     = 120  # Temporarily increased to 120s to debug long model load
}

# Application environment variables

variable "qdrant_type" {
  description = "Qdrant connection type ('cloud' or 'local')"
  type        = string
  default     = "cloud"
}

variable "qdrant_cloud_url" {
  description = "URL of the Qdrant Cloud cluster"
  type        = string
}

variable "qdrant_cloud_api_key" {
  description = "API key for the Qdrant Cloud cluster"
  type        = string
  sensitive   = true
}

variable "llm_provider" {
  description = "LLM provider for agent routing ('openai')"
  type        = string
  default     = "openai"
}

variable "openai_api_key" {
  description = "API key for OpenAI"
  type        = string
  sensitive   = true
}

variable "openai_model" {
  description = "OpenAI model to use (e.g., 'gpt-4o-mini')"
  type        = string
  default     = "gpt-4o-mini"
}
