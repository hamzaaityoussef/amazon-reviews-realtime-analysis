from pymongo import MongoClient
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
import json
import time

# Setup MongoDB
mongo_client = MongoClient("mongodb://mongodb:27017/")
db = mongo_client.amazon_reviews
collection = db.reviews

def create_consumer():
    max_retries = 10
    retry_interval = 5  # seconds
    for attempt in range(max_retries):
        try:
            consumer = KafkaConsumer(
                'amazon-reviews',
                bootstrap_servers=['kafka:9093'],
                auto_offset_reset='earliest',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            print("Kafka consumer connected successfully")
            return consumer
        except NoBrokersAvailable as e:
            print(f"Attempt {attempt + 1}/{max_retries}: No brokers available, retrying in {retry_interval}s...")
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                raise Exception("Failed to connect to Kafka after multiple retries")

def save_to_mongo():
    consumer = create_consumer()
    print("MongoDB consumer started...")
    for message in consumer:
        try:
            data = message.value
            collection.insert_one(data)
            identifier = data.get('polarity', 'unknown')
            print(f"Saved: polarity={identifier}")
        except KeyError as e:
            print(f"Missing key: {str(e)}")
        except Exception as e:
            print(f"Failed to save: {str(e)}")

if __name__ == "__main__":
    save_to_mongo()