import base64
import json
import os
import datetime
import boto3
import pg8000.native

# Environment Variables set by Terraform
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
DB_HOST = os.environ.get("DB_HOST")
DYNAMO_URL = os.environ.get("LOCALSTACK_DYNAMODB_URL")

def init_db():
    """Establish connection to Cloud SQL and ensure the table exists."""
    con = pg8000.native.Connection(
        user=DB_USER, 
        password=DB_PASS, 
        database=DB_NAME, 
        host=DB_HOST
    )
    # Create table if it doesn't exist (Terraform creates the DB, but we need to create the table) [cite: 235-249]
    create_table_query = """
    CREATE TABLE IF NOT EXISTS records (
        id VARCHAR(255) PRIMARY KEY NOT NULL,
        user_email VARCHAR(255) NOT NULL,
        value INTEGER NOT NULL,
        processed_at TIMESTAMP NOT NULL
    );
    """
    con.run(create_table_query)
    return con

def process_event(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic. [cite: 119-120]"""
    print("Function triggered by Pub/Sub!")
    
    try:
        # 1. Decode the Pub/Sub message [cite: 122-124]
        if 'data' in event:
            pubsub_message = base64.b64decode(event['data']).decode('utf-8')
            print(f"Decoded message: {pubsub_message}")
            data = json.loads(pubsub_message)
        else:
            print("No data found in event.")
            return

        # 2. Transform: Add processed_timestamp [cite: 125]
        record_id = data.get('recordId')
        user_email = data.get('userEmail')
        value = data.get('value')
        processed_at = datetime.datetime.utcnow().isoformat()

        # 3. Write to Cloud SQL [cite: 126]
        print("Connecting to Cloud SQL...")
        db_conn = init_db()
        insert_query = """
        INSERT INTO records (id, user_email, value, processed_at) 
        VALUES (:id, :email, :val, :pat)
        ON CONFLICT (id) DO NOTHING;  -- Idempotency check [cite: 142-143]
        """
        db_conn.run(insert_query, id=record_id, email=user_email, val=value, pat=processed_at)
        db_conn.close()
        print("Successfully written to Cloud SQL.")

        # 4. Write to LocalStack DynamoDB [cite: 127]
        print(f"Connecting to DynamoDB at {DYNAMO_URL}...")
        dynamodb = boto3.client(
            'dynamodb',
            endpoint_url=DYNAMO_URL,
            region_name='us-east-1',
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        dynamodb.put_item(
            TableName='processed-records',
            Item={
                'recordId': {'S': str(record_id)},
                'userEmail': {'S': str(user_email)},
                'value': {'N': str(value)},
                'processedAt': {'S': str(processed_at)}
            }
        )
        print("Successfully written to DynamoDB.")

    except Exception as e:
        print(f"Error processing event: {e}")
        raise e