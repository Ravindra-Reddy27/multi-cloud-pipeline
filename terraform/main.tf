# ---------------------------------------------------------
# AWS RESOURCES (LocalStack)
# ---------------------------------------------------------

# 1. S3 Bucket
resource "aws_s3_bucket" "local_bucket" {
  bucket = "hybrid-cloud-bucket"
}

# 2. SQS Queue (THIS WAS MISSING!)
resource "aws_sqs_queue" "local_queue" {
  name = "data-processing-queue"
}

# Grant S3 permission to send messages to the SQS queue
resource "aws_sqs_queue_policy" "local_queue_policy" {
  queue_url = aws_sqs_queue.local_queue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = "*"
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.local_queue.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_s3_bucket.local_bucket.arn
          }
        }
      }
    ]
  })
}

# Tell S3 to notify SQS when a new object is created
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.local_bucket.id

  queue {
    queue_arn = aws_sqs_queue.local_queue.arn
    events    = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_sqs_queue_policy.local_queue_policy]
}

# 3. DynamoDB Table
resource "aws_dynamodb_table" "local_table" {
  name           = "processed-records"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "recordId"

  attribute {
    name = "recordId"
    type = "S"
  }
}

# ---------------------------------------------------------
# GCP RESOURCES
# ---------------------------------------------------------

# 4. Pub/Sub Topic
resource "google_pubsub_topic" "gcp_topic" {
  name = "localstack-events"
}

# 5. Cloud SQL Instance (PostgreSQL)
resource "google_sql_database_instance" "postgres_instance" {
  name             = "hybrid-pipeline-sql-instance-${random_id.db_name_suffix.hex}"
  database_version = "POSTGRES_14"
  region           = var.gcp_region
  deletion_protection = false 

  settings {
    tier = "db-f1-micro" 
    
    # NEW: Open the firewall so the Cloud Function can reach it
    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        name  = "allow-all"
        value = "0.0.0.0/0"
      }
    }
  }
}
resource "random_id" "db_name_suffix" {
  byte_length = 4
}

resource "google_sql_database" "database" {
  name     = "pipelinedb"
  instance = google_sql_database_instance.postgres_instance.name
}

resource "google_sql_user" "users" {
  name     = var.db_user
  instance = google_sql_database_instance.postgres_instance.name
  password = var.db_pass
}

# 6. Cloud Function Resources
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "function_bucket" {
  name          = "${var.gcp_project_id}-func-source-${random_id.bucket_suffix.hex}"
  location      = var.gcp_region
  force_destroy = true
}

data "archive_file" "function_zip" {
  type        = "zip"
  source_dir  = "../src/gcp_function"
  output_path = "/tmp/function_source.zip"
}

resource "google_storage_bucket_object" "function_archive" {
  name   = "function-source-${data.archive_file.function_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name
  source = data.archive_file.function_zip.output_path
}

resource "google_cloudfunctions_function" "processor_function" {
  name        = "hybrid-processor-function"
  description = "Processes events from LocalStack"
  runtime     = "python39"

  available_memory_mb   = 256
  source_archive_bucket = google_storage_bucket.function_bucket.name
  source_archive_object = google_storage_bucket_object.function_archive.name
  
  entry_point           = "process_event"

  event_trigger {
    event_type = "google.pubsub.topic.publish"
    resource   = google_pubsub_topic.gcp_topic.name
  }
  
  environment_variables = {
    DB_HOST                 = google_sql_database_instance.postgres_instance.public_ip_address
    DB_USER                 = var.db_user
    DB_PASS                 = var.db_pass
    DB_NAME                 = var.db_name
    LOCALSTACK_DYNAMODB_URL = var.localstack_dynamodb_url
  }
}