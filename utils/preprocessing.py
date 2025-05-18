import re
import string
from pyspark.sql.functions import udf, col
from pyspark.sql.types import StringType, FloatType
from textblob import TextBlob
from pyspark.ml.feature import Tokenizer, HashingTF, IDF

# Liste des mots vides (stop words) utilisée dans le notebook
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
    """
    Nettoie le texte en supprimant les caractères indésirables, les URL, la ponctuation, etc.
    """
    if not text or text.isspace():
        return ""
    text = str(text).lower()
    text = re.sub(r'\[.*?\]', '', text)  # Supprimer les crochets
    text = re.sub(r'https?://\S+|www\.\S+', '', text)  # Supprimer les URL
    text = re.sub(r'<.*?>+', '', text)  # Supprimer les balises HTML
    text = re.sub(r'[%s]' % re.escape(string.punctuation), '', text)  # Supprimer la ponctuation
    text = re.sub(r'\n', '', text)  # Supprimer les sauts de ligne
    text = re.sub(r'\w*\d\w*', '', text)  # Supprimer les mots contenant des chiffres
    return text

def remove_stopwords(text):
    """
    Supprime les mots vides du texte.
    """
    if not text or text.isspace():
        return ""
    words = text.split()
    filtered = [word for word in words if word not in STOP_WORDS]
    return ' '.join(filtered)

def get_polarity(text):
    """
    Calcule la polarité du texte avec TextBlob.
    """
    try:
        return float(TextBlob(str(text)).sentiment.polarity)
    except:
        return 0.0

# Enregistrement des UDF pour Spark
clean_review_udf = udf(clean_review, StringType())
remove_stopwords_udf = udf(remove_stopwords, StringType())
polarity_udf = udf(get_polarity, FloatType())

def preprocess_text(spark, text_data, include_polarity=True):
    """
    Prétraitement du texte pour le rendre compatible avec le modèle.
    Args:
        spark: Session Spark
        text_data: Liste de chaînes de texte ou DataFrame avec une colonne 'text'
        include_polarity: Si True, calcule la polarité
    Returns:
        DataFrame avec les colonnes prétraitées et les features TF-IDF
    """
    # Si text_data est une liste, créer un DataFrame
    if isinstance(text_data, list):
        df = spark.createDataFrame([(text,) for text in text_data], ["text"])
    else:
        df = text_data

    # Nettoyage du texte
    df = df.withColumn("cleaned_text", clean_review_udf(col("text")))
    
    # Suppression des mots vides
    df = df.withColumn("processed_text", remove_stopwords_udf(col("cleaned_text")))
    
    # Calcul de la polarité (optionnel)
    if include_polarity:
        df = df.withColumn("polarity", polarity_udf(col("processed_text")))
    
    # Pipeline de transformation pour TF-IDF
    tokenizer = Tokenizer(inputCol="processed_text", outputCol="words")
    hashing_tf = HashingTF(inputCol="words", outputCol="raw_features", numFeatures=10000)
    idf = IDF(inputCol="raw_features", outputCol="tfidf")
    
    # Créer et appliquer le pipeline
    pipeline = Pipeline(stages=[tokenizer, hashing_tf, idf])
    pipeline_model = pipeline.fit(df)
    df_transformed = pipeline_model.transform(df)
    
    return df_transformed