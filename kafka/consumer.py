from pymongo import MongoClient
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from pyspark.sql import SparkSession
from pyspark.ml.classification import LogisticRegressionModel
from pyspark.ml.feature import Tokenizer, HashingTF, IDF, IDFModel
from pyspark.sql.functions import udf, col
from pyspark.sql.types import ArrayType, StringType
from pyspark.ml import Pipeline
import spacy
import json
import time
import logging
import os
from utils.preprocessing import preprocess_text

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Spark
logger.info("Initializing Spark session")
spark = SparkSession.builder \
    .appName("ReviewConsumer") \
    .master("local[*]") \
    .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "2g")) \
    .config("spark.executor.memory", os.getenv("SPARK_WORKER_MEMORY", "2g")) \
    .config("spark.python.worker.connectionTimeout", "60000") \
    .getOrCreate()
logger.info(f"Spark version: {spark.version}")

# Define lemmatization UDF
def lemmatize(tokens):
    if not tokens or not isinstance(tokens, (list, tuple)) or len(tokens) == 0:
        return []
    try:
        # Load spaCy model inside the UDF to avoid serialization issues
        nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])  # Disable unused components for performance
        text = " ".join([t for t in tokens if isinstance(t, str)])
        doc = nlp(text)
        return [token.lemma_ for token in doc if not token.is_punct]
    except Exception as e:
        logger.error(f"Error in lemmatize UDF: {str(e)}")
        return []

lemmatize_udf = udf(lemmatize, ArrayType(StringType()))

# Load the IDF model
idf_model_path = "/app/model/idf_model"
logger.info(f"Loading IDF model from {idf_model_path}")
try:
    if not os.path.exists(idf_model_path):
        logger.error(f"IDF model path does not exist: {idf_model_path}")
        spark.stop()
        exit(1)
    idf_model = IDFModel.load(idf_model_path)
    logger.info("IDF model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load IDF model: {str(e)}")
    spark.stop()
    exit(1)

# Load the LogisticRegression model
model_path = "/app/model/logistic_regression_model"
logger.info(f"Loading model from {model_path}")
try:
    model = LogisticRegressionModel.load(model_path)
    logger.info("Model loaded successfully")
    print()
except Exception as e:
    logger.error(f"Failed to load model: {str(e)}")
    raise

# Setup MongoDB
logger.info("Connecting to MongoDB")
mongo_client = MongoClient("mongodb://mongodb:27017/")
db = mongo_client.amazon_reviews
collection = db.reviews
logger.info(f"Connected to MongoDB database: {db.name}")

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
            logger.info("Kafka consumer connected successfully")
            return consumer
        except NoBrokersAvailable as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries}: No brokers available, retrying in {retry_interval}s...")
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                logger.error("Failed to connect to Kafka after multiple retries")
                raise Exception("Failed to connect to Kafka after multiple retries")

def predict_sentiment(text):
    logger.info(f"Predicting sentiment for text: {text[:50]}...")
    if not text or not isinstance(text, str):
        logger.error("Invalid text input for prediction")
        return "unknown", None
    try:
        df = preprocess_text(spark, [text], include_polarity=True)
        processed_text = df.select("processed_text").collect()[0][0]
        logger.info(f"Preprocessed text: {processed_text}")

        # Use the existing 'tfidf' column from preprocess_text
        df_final = df

        # Make prediction using the preloaded model
        prediction = model.transform(df_final)
        result = prediction.select("prediction").collect()[0][0]
        sentiment_map = {0.0: "positive", 1.0: "neutral", 2.0: "negative"}
        sentiment = sentiment_map.get(result, "unknown")
        logger.info(f"Predicted sentiment: {sentiment}")

        # Extract polarity from the DataFrame
        polarity = df.select("polarity").collect()[0][0]
        return sentiment, polarity
    except Exception as e:
        logger.error(f"Error predicting sentiment: {str(e)}")
        return "unknown", None

def save_to_mongo():
    consumer = create_consumer()
    logger.info("MongoDB consumer started...")
    
    # Initialize or load existing predicted data
    predicted_data_file = "/app/data/predicted_data.json"
    try:
        with open(predicted_data_file, 'r') as f:
            predicted_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        predicted_data = []
        logger.info("Starting with empty predicted data file")
    
    for message in consumer:
        try:
            data = message.value
            logger.info(f"Received message: {data}")
            
            # Save raw data to MongoDB first
            result = collection.insert_one(data)
            doc_id = result.inserted_id
            logger.info(f"Inserted raw data with ID: {doc_id}")
            
            # Add preprocessed fields
            data['predicted_sentiment'], polarity = predict_sentiment(data['reviewText'])
            data['polarity'] = polarity if polarity is not None else 0.0
            
            # Update the same document with preprocessed fields
            collection.update_one({'_id': doc_id}, {'$set': {
                'predicted_sentiment': data['predicted_sentiment'],
                'polarity': data['polarity']
            }})
            logger.info(f"Updated document with ID: {doc_id} - polarity={data['polarity']}, predicted_sentiment={data['predicted_sentiment']}")
            
            # Add to predicted data list
            predicted_data.append({
                'reviewerID': data.get('reviewerID', 'N/A'),
                'asin': data.get('asin', 'N/A'),
                'reviewText': data.get('reviewText', ''),
                'predicted_sentiment': data['predicted_sentiment'],
                'polarity': data['polarity']
            })
            
            # Save to file every 10 reviews to avoid too frequent writes
            if len(predicted_data) % 10 == 0:
                with open(predicted_data_file, 'w') as f:
                    json.dump(predicted_data, f, indent=2)
                logger.info(f"Saved {len(predicted_data)} reviews to predicted_data.json")
                
        except Exception as e:
            logger.error(f"Failed to save or update: {str(e)}")
            
    # Save any remaining reviews at the end
    try:
        with open(predicted_data_file, 'w') as f:
            json.dump(predicted_data, f, indent=2)
        logger.info(f"Final save: {len(predicted_data)} reviews saved to predicted_data.json")
    except Exception as e:
        logger.error(f"Failed to save final predicted data: {str(e)}")

if __name__ == "__main__":
    try:
        save_to_mongo()
    except Exception as e:
        logger.error(f"Consumer failed: {str(e)}")
        spark.stop()
        raise