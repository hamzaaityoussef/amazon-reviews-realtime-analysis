import logging
import spacy
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col
from pyspark.sql.types import ArrayType, StringType
from pyspark.ml.feature import Tokenizer, HashingTF, IDF , IDFModel
from pyspark.ml.classification import LogisticRegressionModel
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Spark
logger.info("Initializing Spark session")
spark = SparkSession.builder \
    .appName("SpacyModelTest") \
    .master("local[*]") \
    .config("spark.driver.memory", "2g") \
    .config("spark.executor.memory", "2g") \
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

# Sample reviews (positive, negative, neutral)
logger.info("Creating sample reviews")
sample_texts = [
    ("This guitar is amazing! I love it!", "positive"),  # Positive
    ("I hate this product, it broke immediately!", "negative"),  # Negative
    ("It's normal, nothing special.", "neutral")  # Neutral
]
df = spark.createDataFrame([(i, text, label) for i, (text, label) in enumerate(sample_texts)], ["id", "reviews", "expected_label"])
logger.info("Sample reviews DataFrame created")

# Tokenize
logger.info("Tokenizing reviews")
tokenizer = Tokenizer(inputCol="reviews", outputCol="words")
df_tokenized = tokenizer.transform(df)

# Lemmatize
logger.info("Lemmatizing tokens")
df_tokenized = df_tokenized.withColumn("lemmatized", lemmatize_udf(col("words")))

# Vectorization
logger.info("Vectorizing lemmatized text")
hashing_tf = HashingTF(inputCol="lemmatized", outputCol="raw_features", numFeatures=10000)
df_featurized = hashing_tf.transform(df_tokenized)

idf = IDF(inputCol="raw_features", outputCol="tfidf")  # LogisticRegressionModel expects "features"
# idf_model = idf.fit(df_featurized)
# df_final = idf_model.transform(df_featurized)

idf_model_path = "./model/idf_model"
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


  # <-- path to the saved model
df_final = idf_model.transform(df_featurized)

# Load model
model_path = "./model/logistic_regression_model"
logger.info(f"Loading model from {model_path}")
try:
    loaded_model = LogisticRegressionModel.load(model_path)
    logger.info("Model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load model: {str(e)}")
    spark.stop()
    exit(1)

# Predict
logger.info("Making predictions")
predictions = loaded_model.transform(df_final)

# Show predictions with expected labels
logger.info("Displaying predictions")
predictions.select("reviews", "expected_label", "prediction", "probability").show(truncate=False)

# Clean up
spark.stop()
logger.info("Spark session stopped")