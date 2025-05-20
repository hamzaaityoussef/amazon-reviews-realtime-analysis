from flask import Flask, render_template
from pymongo import MongoClient
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# MongoDB connection
client = MongoClient("mongodb://mongodb:27017/")
db = client.amazon_reviews
collection = db.reviews

@app.route('/')
def index():
    logger.info("Fetching data from MongoDB")
    reviews = list(collection.find().limit(100))  # Limit to 100 for performance
    
    # Log the structure of the reviews data
    if reviews:
        logger.info("Sample review structure: %s", reviews[0])
        logger.info("All reviews: %s", reviews)
    else:
        logger.warning("No reviews found in MongoDB")
    
    positive = len([r for r in reviews if r.get('predicted_sentiment') == 'positive'])
    negative = len([r for r in reviews if r.get('predicted_sentiment') == 'negative'])
    neutral = len([r for r in reviews if r.get('predicted_sentiment') == 'neutral'])
    return render_template('index.html', reviews=reviews, positive=positive, negative=negative, neutral=neutral)

if __name__ == '__main__':
    logger.info("Starting web server")
    app.run(host='0.0.0.0', port=5000, debug=True)