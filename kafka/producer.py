import json
import time
from kafka import KafkaProducer

DATA_FILE = "data/Musical_Instruments_5.json"

# Initialisation du producteur Kafka
producer = KafkaProducer(
    bootstrap_servers=['127.0.0.1:9092'],  # ou 'kafka:9092' si dans Docker
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

TOPIC_NAME = "amazon-reviews"

def stream_reviews():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                review = json.loads(line.strip())
                producer.send(TOPIC_NAME, value=review)
                print(f"Message envoyé : {review.get('reviewText', '')[:80]}...")
                time.sleep(1)  # Simule un flux en temps réel
            except json.JSONDecodeError:
                print("error")
                continue

if __name__ == "__main__":
    print("📤 Streaming des avis Amazon vers Kafka...")
    stream_reviews()
