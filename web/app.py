from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# MongoDB connection
client = MongoClient("mongodb://mongodb:27017/")
# client = MongoClient("mongodb://localhost:27017/")
db = client.amazon_reviews
collection = db.reviews

@app.route('/')
def index():
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Calculate skip value for pagination
    skip = (page - 1) * per_page
    
    # Fetch paginated reviews
    reviews = list(collection.find({}).skip(skip).limit(per_page))
    
    # Get total count for pagination
    total_reviews = collection.count_documents({})
    total_pages = (total_reviews + per_page - 1) // per_page
    
    # Convert ObjectId to string for JSON serialization if needed
    for review in reviews:
        review['_id'] = str(review['_id'])
        # Also ensure reviewText is included if needed for modal
        if 'reviewText' not in review:
            original_review = collection.find_one({'_id': review['_id']})
            if original_review:
                review['reviewText'] = original_review.get('reviewText', '')

    # Calculate sentiment distribution for the initial load
    positive = len(
        [r for r in reviews if r.get('predicted_sentiment') == 'positive']
    )
    negative = len(
        [r for r in reviews if r.get('predicted_sentiment') == 'negative']
    )
    neutral = len(
        [r for r in reviews if r.get('predicted_sentiment') == 'neutral']
    )
    
    # Calculate page range for pagination
    start_page = max(1, page - 2)
    end_page = min(total_pages + 1, page + 3)
    page_range = range(start_page, end_page)
    
    # Render HTML template with all reviews and pagination info
    return render_template('index.html', 
                         reviews=reviews, 
                         positive=positive, 
                         negative=negative, 
                         neutral=neutral,
                         current_page=page,
                         total_pages=total_pages,
                         per_page=per_page,
                         page_range=page_range)

@app.route('/search')
def search():
    # This route is no longer used after removing search functionality
    return jsonify([])

@app.route('/time_data')
def time_data():
    # Get the last 24 hours of data using unixReviewTime
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)
    
    # Convert datetime to Unix timestamp (seconds)
    start_unix = int(start_time.timestamp())
    end_unix = int(end_time.timestamp())
    
    # Aggregate reviews by ASIN and sentiment
    pipeline = [
        {
            '$match': {
                'unixReviewTime': {
                    '$gte': start_unix,
                    '$lte': end_unix
                }
            }
        },
        {
            '$group': {
                '_id': {
                    'asin': '$asin',
                    'sentiment': '$predicted_sentiment'
                },
                'count': {'$sum': 1}
            }
        },
        {
            '$group': {
                '_id': '$_id.asin',
                'sentiments': {
                    '$push': {
                        'sentiment': '$_id.sentiment',
                        'count': '$count'
                    }
                },
                'total_reviews': {'$sum': '$count'}
            }
        },
        {
            '$sort': {'total_reviews': -1}
        }
    ]
    
    product_data = list(collection.aggregate(pipeline))
    
    # Format the data for the chart
    chart_data = []
    for product in product_data:
        sentiments = {s['sentiment']: s['count'] for s in product['sentiments']}
        chart_data.append({
            'asin': product['_id'],
            'total_reviews': product['total_reviews'],
            'positive': sentiments.get('positive', 0),
            'negative': sentiments.get('negative', 0),
            'neutral': sentiments.get('neutral', 0)
        })
    
    return jsonify(chart_data)

@app.route('/product_sentiment_distribution')
def product_sentiment_distribution():
    # Aggregate total reviews by ASIN for all reviews
    pipeline = [
        {
            '$group': {
                '_id': '$asin',
                'count': {'$sum': 1}
            }
        },
        {
            '$project': {
                '_id': 0,  # Exclude _id
                'asin': '$_id',  # Rename _id to asin
                'total_reviews': '$count'
            }
        },
        {
            '$sort': {'total_reviews': -1} # Sort by total reviews descending
        }
    ]
    
    product_data = list(collection.aggregate(pipeline))
    
    return jsonify(product_data)

@app.route('/recent_reviews')
def recent_reviews():
    # Get the last hour of reviews using unixReviewTime
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)
    
    # Convert datetime to Unix timestamp (seconds)
    start_unix = int(start_time.timestamp())
    end_unix = int(end_time.timestamp())

    # Query reviews within the time range using unixReviewTime
    # Exclude large fields like reviewText, helpful, summary initially for performance
    reviews = list(collection.find({
        'unixReviewTime': {
            '$gte': start_unix,
            '$lte': end_unix
        }
    }, {'_id': 1, 'reviewerID': 1, 'asin': 1, 'predicted_sentiment': 1, 'polarity': 1, 'unixReviewTime': 1}))
    
    # Prepare data for frontend - fetch reviewText separately if needed for modal
    processed_reviews = []
    for review in reviews:
        # Convert unixReviewTime to ISO format string for the frontend
        timestamp = datetime.fromtimestamp(review['unixReviewTime'], tz=timezone.utc)
        
        # Fetch full review details including reviewText for the modal
        full_review = collection.find_one({'_id': review['_id']})
        review_text = full_review.get('reviewText', '') if full_review else ''

        processed_reviews.append({
            '_id': str(review['_id']),
            'reviewerID': review.get('reviewerID'),
            'asin': review.get('asin'),
            'predicted_sentiment': review.get('predicted_sentiment'),
            'polarity': review.get('polarity'),
            'timestamp': timestamp.isoformat(), # Use consistent 'timestamp' field name for frontend
            'reviewText': review_text # Include reviewText here as it's needed for modal
        })
    
    return jsonify(processed_reviews)

@app.route('/asin_review_counts')
def asin_review_counts():
    # Aggregate to count reviews per ASIN
    pipeline = [
        {
            '$group': {
                '_id': '$asin',
                'count': {'$sum': 1}
            }
        },
        {
            '$project': {
                '_id': 0,  # Exclude _id
                'asin': '$_id',  # Rename _id to asin
                'count': 1
            }
        },
        {
            '$sort': {'asin': 1}  # Sort by ASIN
        }
    ]
    
    asin_counts = list(collection.aggregate(pipeline))
    
    return jsonify(asin_counts)

@app.route('/export')
def export():
    reviews = list(collection.find())
    # Convert ObjectId to string and datetime/unix timestamp to string for JSON serialization
    processed_reviews = []
    for review in reviews:
        processed_review = review.copy()
        processed_review['_id'] = str(review['_id'])
        if 'timestamp' in review and isinstance(review['timestamp'], datetime):
             processed_review['timestamp'] = review['timestamp'].isoformat()
        elif 'unixReviewTime' in review and isinstance(review['unixReviewTime'], (int, float)):
             processed_review['timestamp'] = datetime.fromtimestamp(review['unixReviewTime'], tz=timezone.utc).isoformat()
        processed_reviews.append(processed_review)

    return jsonify(processed_reviews)

if __name__ == '__main__':
    logger.info("Starting web server")
    # Consider setting use_reloader=False to prevent multiple Flask instances in development
    # app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    app.run(host='0.0.0.0', port=5000, debug=True)