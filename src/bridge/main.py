import boto3
import json
import time
import os
import urllib.parse
from google.cloud import pubsub_v1

# Configuration
AWS_ENDPOINT = "http://localstack:4566"
QUEUE_NAME = "data-processing-queue"
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
TOPIC_ID = "localstack-events"

def get_aws_client(service):
    return boto3.client(
        service,
        endpoint_url=AWS_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )

def main():
    print("Bridge Application Started...")
    sqs = get_aws_client("sqs")
    s3 = get_aws_client("s3")
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GCP_PROJECT_ID, TOPIC_ID)

    try:
        response = sqs.get_queue_url(QueueName=QUEUE_NAME)
        queue_url = response['QueueUrl']
        print(f"Connected to SQS: {queue_url}")
    except Exception as e:
        print(f"Error connecting to SQS: {e}")
        return

    print("Polling for messages...")
    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10
            )

            if 'Messages' in response:
                for msg in response['Messages']:
                    print(f"Received SQS message: {msg['MessageId']}")
                    body = json.loads(msg['Body'])

                    # 1. Check if this is an S3 Event Notification
                    if 'Records' in body and 's3' in body['Records'][0]:
                        s3_event = body['Records'][0]['s3']
                        bucket_name = s3_event['bucket']['name']
                        object_key = urllib.parse.unquote_plus(s3_event['object']['key'])
                        
                        # 2. Download the actual file from LocalStack S3
                        print(f"Fetching file {object_key} from bucket {bucket_name}...")
                        s3_response = s3.get_object(Bucket=bucket_name, Key=object_key)
                        file_content = s3_response['Body'].read().decode('utf-8')
                        
                        # The payload is now the actual file contents
                        payload_bytes = file_content.encode("utf-8")
                    else:
                        # Fallback (just in case)
                        payload_bytes = json.dumps(body).encode("utf-8")

                    # 3. Publish the file contents to GCP Pub/Sub
                    future = publisher.publish(topic_path, payload_bytes)
                    print(f"Published to GCP Pub/Sub: {future.result()}")

                    # 4. Delete the notification from SQS
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=msg['ReceiptHandle']
                    )
                    print("Message deleted from SQS.")
            
        except Exception as e:
            print(f"Error in processing loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()