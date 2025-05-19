from pymongo import MongoClient
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from pyspark.sql import SparkSession
from pyspark.ml import LogisticRegressionModel, PipelineModel
from pyspark.ml.feature import Tokenizer, HashingTF, IDF, IDFModel
from pyspark.sql.functions import udf, col
from pyspark.sql.types import ArrayType, StringType
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
    .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "1g")) \
    .config("spark.executor.memory", os.getenv("SPARK_WORKER_MEMORY", "1g")) \
    .config("spark.python.worker.connectionTimeout", "60000") \
    .getOrCreate()
logger.info(f"Spark version: {spark.version}")

# Load spaCy model
logger.info("Loading spaCy model")
try:
    nlp = spacy.load("en_core_web_sm")
    logger.info("spaCy model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load spaCy model: {str(e)}")
    spark.stop()
    exit(1)

# Define lemmatization UDF
def lemmatize(tokens):
    if not tokens or not isinstance(tokens, (list, tuple)) or len(tokens) == 0:
        return []
    text = " ".join([t for t in tokens if isinstance(t, str)])
    doc = nlp(text)
    return [token.lemma_ for token in doc if not token.is_punct]

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
    try:
        # Preprocess the text using the provided utility
        df = preprocess_text(spark, [text], include_polarity=True)
        
        # Log preprocessed text
        processed_text = df.select("processed_text").collect()[0][0]
        logger.info(f"Preprocessed text: {processed_text}")

        # Tokenize
        tokenizer = Tokenizer(inputCol="processed_text", outputCol="words")
        df_tokenized = tokenizer.transform(df)

        # Lemmatize
        df_tokenized = df_tokenized.withColumn("lemmatized", lemmatize_udf(col("words")))

        # Vectorization with HashingTF
        hashing_tf = HashingTF(inputCol="lemmatized", outputCol="raw_features", numFeatures=10000)
        df_featurized = hashing_tf.transform(df_tokenized)

        # Transform with IDF
        df_final = idf_model.transform(df_featurized)

        # Rename 'tfidf' to 'features' (LogisticRegressionModel expects 'features')
        df_final = df_final.withColumnRenamed("tfidf", "features")

        # Make prediction
        prediction = model.transform(df_final)
        result = prediction.select("prediction").collect()[0][0]
        sentiment_map = {0.0: "negative", 1.0: "positive", 2.0: "neutral"}
        sentiment = sentiment_map.get(result, "unknown")
        logger.info(f"Predicted sentiment: {sentiment}")
        return sentiment
    except Exception as e:
        logger.error(f"Error predicting sentiment: {str(e)}")
        return "unknown"

def save_to_mongo():
    consumer = create_consumer()
    logger.info("MongoDB consumer started...")
    for message in consumer:
        try:
            data = message.value
            logger.info(f"Received message: {data}")
            # Add sentiment prediction if text is available
            if 'text' in data:
                data['predicted_sentiment'] = predict_sentiment(data['text'])
                # Add polarity
                df = preprocess_text(spark, [data['text']], include_polarity=True)
                polarity = df.select("polarity").collect()[0][0]
                data['polarity'] = polarity
            # Save to MongoDB (uncomment when ready)
            # collection.insert_one(data)
            identifier = data.get('polarity', 'unknown')
            logger.info(f"Saved: polarity={identifier}, predicted_sentiment={data.get('predicted_sentiment', 'unknown')}")
        except KeyError as e:
            logger.error(f"Missing key: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to save: {str(e)}")

if __name__ == "__main__":
    try:
        save_to_mongo()
    except Exception as e:
        logger.error(f"Consumer failed: {str(e)}")
        spark.stop()
        raise