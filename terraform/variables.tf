variable "gcp_project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "gcp_region" {
  description = "The region for GCP resources"
  type        = string
  default     = "us-central1"
}

variable "gcp_keyfile_path" {
  description = "Path to the GCP JSON key file"
  type        = string
}
variable "db_user" {
  description = "The database username"
  type        = string
  default     = "postgres"
}

variable "db_pass" {
  description = "The database password"
  type        = string
  sensitive   = true  # This hides the password in the terminal logs
}

variable "db_name" {
  description = "The name of the database"
  type        = string
  default     = "pipelinedb"
}

variable "localstack_dynamodb_url" {
  description = "The public URL (Ngrok) for LocalStack DynamoDB"
  type        = string
}