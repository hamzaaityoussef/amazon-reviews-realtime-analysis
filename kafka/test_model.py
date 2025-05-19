import logging
from pyspark.sql import SparkSession
from pyspark.ml.classification import LogisticRegressionModel
from pyspark.sql.functions import col
from pyspark.sql.types import StringType, FloatType
import re
import string
from textblob import TextBlob
from pyspark.ml.feature import Tokenizer, HashingTF, IDF
from pyspark.sql.functions import udf

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Spark
logger.info("Initializing Spark session")
spark = SparkSession.builder \
    .appName("ModelTest") \
    .master("local[*]") \
    .config("spark.driver.memory", "1g") \
    .config("spark.executor.memory", "1g") \
    .getOrCreate()
logger.info(f"Spark version: {spark.version}")

# Define preprocessing functions (from preprocess.py)
STOP_WORDS = [
    'yourselves', 'between', 'whom', 'itself', 'is', "she's", 'up', 'herself', 'here', 'your', 'each',
    'we', 'he', 'my', "you've", 'having', 'in', 'both', 'for', 'themselves', 'are', 'them', 'other',
    'and', 'an', 'during', 'their', 'can', 'yourself', 'she', 'until', 'so', 'these', 'ours', 'above',
    'what', 'while', 'have', 're', 'more', 'only', "needn't", 'when', 'just', 'that', 'were', "don't",
    'very', 'should', 'any', 'y', 'isn', 'who', 'a', 'they', 'to', 'too', "should've", 'has', 'before',
    'into', 'yours', "it's", 'do', 'against', 'on', 'now', 'her', 've', 'd', 'by', 'am', 'from',
    'about', 'further', "that'll", "you'd", 'you', 'as', 'how', 'been', 'the', 'or', 'doing', 'such',
    'his', 'himself', 'ourselves', 'was', 'through', 'out', 'below', 'own', 'myself', 'theirs',
    'me', 'why', 'once', 'him', 'than', 'be', 'most', "you'll", 'same', 'some', 'with', 'few', 'it',
    'at', 'after', 'its', 'which', 'there', 'our', 'this', 'hers', 'being', 'did', 'of', 'had', 'under',
    'over', 'again', 'where', 'those', 'then', "you're", 'i', 'because', 'does', 'all'
]

def clean_review(text):
    if not text or text.isspace():
        return ""
    text = str(text).lower()
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'<.*?>+', '', text)
    text = re.sub(r'[%s]' % re.escape(string.punctuation), '', text)
    text = re.sub(r'\n', '', text)
    text = re.sub(r'\w*\d\w*', '', text)
    return text

def remove_stopwords(text):
    if not text or text.isspace():
        return ""
    words = text.split()
    filtered = [word for word in words if word not in STOP_WORDS]
    return ' '.join(filtered)

def get_polarity(text):
    try:
        return float(TextBlob(str(text)).sentiment.polarity)
    except:
        return 0.0

# Register UDFs
clean_review_udf = udf(clean_review, StringType())
remove_stopwords_udf = udf(remove_stopwords, StringType())
polarity_udf = udf(get_polarity, FloatType())

def preprocess_text(spark, text_data, include_polarity=True):
    logger.info("Preprocessing text")
    if isinstance(text_data, list):
        df = spark.createDataFrame([(text,) for text in text_data], ["text"])
    else:
        df = text_data

    df = df.withColumn("cleaned_text", clean_review_udf(col("text")))
    df = df.withColumn("processed_text", remove_stopwords_udf(col("cleaned_text")))
    if include_polarity:
        df = df.withColumn("polarity", polarity_udf(col("processed_text")))
    
    tokenizer = Tokenizer(inputCol="processed_text", outputCol="words")
    hashing_tf = HashingTF(inputCol="words", outputCol="raw_features", numFeatures=10000)
    idf = IDF(inputCol="raw_features", outputCol="tfidf")
    
    pipeline = Pipeline(stages=[tokenizer, hashing_tf, idf])
    pipeline_model = pipeline.fit(df)
    df_transformed = pipeline_model.transform(df)
    
    return df_transformed

def predict_sentiment(model, text):
    logger.info(f"Predicting sentiment for text: {text[:50]}...")
    try:
        df = preprocess_text(spark, [text], include_polarity=True)
        processed_text = df.select("processed_text").collect()[0][0]
        logger.info(f"Preprocessed text: {processed_text}")
        
        prediction = model.transform(df)
        result = prediction.select("prediction").collect()[0][0]
        sentiment_map = {0.0: "negative", 1.0: "positive", 2.0: "neutral"}
        sentiment = sentiment_map.get(result, "unknown")
        polarity = df.select("polarity").collect()[0][0]
        logger.info(f"Predicted sentiment: {sentiment}, Polarity: {polarity}")
        return sentiment, polarity
    except Exception as e:
        logger.error(f"Error predicting sentiment: {str(e)}")
        return "unknown", 0.0

# Load and test the model
model_path = "./model/logistic_regression_model"
logger.info(f"Loading model from {model_path}")
try:
    model = LogisticRegressionModel.load(model_path)
    logger.info("Model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load model: {str(e)}")
    spark.stop()
    exit(1)

# Test with sample texts
sample_texts = [
    "This guitar is amazing! I love it!",
    "The product was terrible and broke after one use.",
    "It's okay, nothing special."
]

for text in sample_texts:
    sentiment, polarity = predict_sentiment(model, text)
    print(f"Text: {text}")
    print(f"Sentiment: {sentiment}, Polarity: {polarity}\n")

# Clean up
spark.stop()
logger.info("Spark session stopped")