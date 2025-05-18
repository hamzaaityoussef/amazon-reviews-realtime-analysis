from pymongo import MongoClient
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel
import json
import time
from utils.preprocessing import preprocess_text  # Importer le module de prétraitement

# Initialize Spark
spark = SparkSession.builder \
    .appName("ReviewConsumer") \
    .master("local[*]") \
    .getOrCreate()

# Load the model
model_path = "/app/model/logistic_regression_model"
model = PipelineModel.load(model_path)

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

def predict_sentiment(text):
    """
    Prédit le sentiment d'un texte en appliquant le prétraitement et le modèle.
    """
    try:
        # Prétraiter le texte
        df = preprocess_text(spark, [text], include_polarity=True)
        
        # Faire la prédiction
        prediction = model.transform(df)
        
        # Récupérer le résultat de la prédiction
        result = prediction.select("prediction").collect()[0][0]
        
        # Mapper la prédiction numérique au sentiment
        sentiment_map = {0.0: "negative", 1.0: "positive", 2.0: "neutral"}
        return sentiment_map.get(result, "unknown")
    except Exception as e:
        print(f"Error predicting sentiment: {str(e)}")
        return "unknown"

def save_to_mongo():
    consumer = create_consumer()
    print("MongoDB consumer started...")
    for message in consumer:
        try:
            data = message.value
            # Ajouter la prédiction de sentiment si le texte est disponible
            if 'text' in data:
                data['predicted_sentiment'] = predict_sentiment(data['text'])
                # Ajouter la polarité si elle a été calculée
                df = preprocess_text(spark, [data['text']], include_polarity=True)
                polarity = df.select("polarity").collect()[0][0]
                data['polarity'] = polarity
            # Sauvegarder dans MongoDB
            collection.insert_one(data)
            identifier = data.get('polarity', 'unknown')
            print(f"Saved: polarity={identifier}, predicted_sentiment={data.get('predicted_sentiment', 'unknown')}")
        except KeyError as e:
            print(f"Missing key: {str(e)}")
        except Exception as e:
            print(f"Failed to save: {str(e)}")

if __name__ == "__main__":
    save_to_mongo()