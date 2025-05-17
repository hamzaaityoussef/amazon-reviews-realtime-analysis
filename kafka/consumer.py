from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StringType, IntegerType, ArrayType
from pyspark.ml.feature import HashingTF, IDFModel
from pyspark.ml.classification import LogisticRegressionModel
from pymongo import MongoClient

# Créer la Spark session
spark = SparkSession.builder \
    .appName("KafkaReviewConsumer") \
    .master("local[*]") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Schéma des données JSON envoyées par Kafka
schema = StructType() \
    .add("reviewText", StringType()) \
    .add("overall", IntegerType()) \
    .add("asin", StringType()) \
    .add("reviewTime", StringType()) \
    .add("reviewerID", StringType())

# Lire le stream Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9093") \
    .option("subscribe", "amazon-reviews") \
    .option("startingOffsets", "latest") \
    .load()

# Convertir en chaîne, puis JSON
reviews = df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")

# Charger le modèle TF-IDF (si sauvegardé séparément)
# tfidf_model = IDFModel.load("chemin/vers/tfidf_model")

# Charger le modèle de classification
model = LogisticRegressionModel.load("/app/logistic_regression_model")

# Pour la démo : simuler un champ features (doit être vectorisé comme dans l'entraînement)
from pyspark.ml.feature import Tokenizer, StopWordsRemover, HashingTF

tokenizer = Tokenizer(inputCol="reviewText", outputCol="words")
stop_remover = StopWordsRemover(inputCol="words", outputCol="filtered")
hashingTF = HashingTF(inputCol="filtered", outputCol="tfidf", numFeatures=1000)

from pyspark.ml import Pipeline
pipeline = Pipeline(stages=[tokenizer, stop_remover, hashingTF])

prepped_data = pipeline.fit(reviews).transform(reviews)

# Prédiction
predictions = model.transform(prepped_data)

# Sélectionner les colonnes pertinentes
result = predictions.select("asin", "reviewText", "prediction", "reviewTime")

# Fonction pour écrire dans MongoDB
def write_to_mongo(df, epoch_id):
    results = df.toPandas().to_dict(orient="records")
    client = MongoClient("mongodb://mongodb:27017/")
    db = client.amazon_reviews
    collection = db.predictions
    collection.insert_many(results)

# Lancer le streaming avec MongoDB sink
query = result.writeStream \
    .foreachBatch(write_to_mongo) \
    .outputMode("append") \
    .start()

query.awaitTermination()
