import json
from kafka import KafkaConsumer

# Initialisation du consommateur Kafka
consumer = KafkaConsumer(
    'amazon-reviews',
    bootstrap_servers=['localhost:9092'],  # ou 'kafka:9092' si dans Docker
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='test-consumer-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

print("📥 En attente de messages depuis le topic 'amazon-reviews'...")
for message in consumer:
    review = message.value
    print(f"Reçu : {review.get('reviewText', '')[:80]}...")
