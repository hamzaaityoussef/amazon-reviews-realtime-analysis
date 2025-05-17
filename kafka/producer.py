import json
import time
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

DATA_FILE = "data/test.json"
TOPIC_NAME = "amazon-reviews"

def create_producer():
    max_retries = 10
    retry_interval = 5  # seconds
    for attempt in range(max_retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers=['kafka:9093'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print("Kafka producer connected successfully")
            return producer
        except NoBrokersAvailable as e:
            print(f"Attempt {attempt + 1}/{max_retries}: No brokers available, retrying in {retry_interval}s...")
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                raise Exception("Failed to connect to Kafka after multiple retries")

def stream_reviews():
    producer = create_producer()
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                review = json.loads(line.strip())
                producer.send(TOPIC_NAME, value=review)
                # Check for reviewerID or fallback to another field
                if 'reviewerID' in review:
                    print(f"Sent: {review['reviewerID'][:8]}...")
                else:
                    print(f"Sent: polarity={review.get('polarity', 'unknown')}")
                time.sleep(0.1)
            except Exception as e:
                print(f"Error: {str(e)}")
                continue

if __name__ == "__main__":
    print("Starting file reader producer...")
    stream_reviews()