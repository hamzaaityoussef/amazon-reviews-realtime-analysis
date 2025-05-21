from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import logging
import sys
import os
import json
from datetime import datetime, timezone, timedelta

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# MongoDB connection
client = MongoClient("mongodb://mongodb:27017/")
# client = MongoClient("mongodb://localhost:27017/")
db = client.amazon_reviews
collection = db.reviews

# Global variable to track the last review index
last_review_index = 0

def load_predicted_data():
    try:
        with open('/app/data/predicted_data.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading predicted data: {e}")
        return []

@app.route('/')
def index():
    # For the main page, we'll just render the template
    # The data will be loaded via AJAX calls
    return render_template('index.html')

@app.route('/offline-dashboard')
def offline_dashboard():
    # Load data from JSON file
    reviews = load_predicted_data()
    
    # Calculate sentiment distribution
    positive = sum(1 for r in reviews if r.get('predicted_sentiment') == 'positive')
    negative = sum(1 for r in reviews if r.get('predicted_sentiment') == 'negative')
    neutral = sum(1 for r in reviews if r.get('predicted_sentiment') == 'neutral')
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total_pages = (len(reviews) + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Get current page reviews
    current_reviews = reviews[start_idx:end_idx]
    
    # Calculate page range for pagination
    page_range = list(range(max(1, page - 2), min(total_pages + 1, page + 3)))
    
    return render_template('offline_dashboard.html',
                         reviews=current_reviews,
                         positive=positive, 
                         negative=negative, 
                         neutral=neutral,
                         current_page=page,
                         total_pages=total_pages,
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
    global last_review_index
    try:
        # Load the latest data
        reviews = load_predicted_data()
        
        if not reviews:
            return jsonify({
                'reviews': [],
                'sentiment_counts': {'positive': 0, 'negative': 0, 'neutral': 0, 'total': 0},
                'product_counts': []
            })
        
        # Get the next review
        if last_review_index >= len(reviews):
            last_review_index = 0  # Reset to start if we've shown all reviews
        
        current_review = reviews[last_review_index]
        last_review_index += 1
        
        # Calculate sentiment distribution for all reviews
        total_positive = sum(1 for r in reviews if r.get('predicted_sentiment', '').lower() == 'positive')
        total_negative = sum(1 for r in reviews if r.get('predicted_sentiment', '').lower() == 'negative')
        total_neutral = sum(1 for r in reviews if r.get('predicted_sentiment', '').lower() == 'neutral')
        total_reviews = len(reviews)
        
        # Calculate product counts for all reviews
        product_counts = {}
        for review in reviews:
            asin = review.get('asin')
            if asin:
                product_counts[asin] = product_counts.get(asin, 0) + 1
        
        # Get top 10 products
        top_products = [
            {'asin': asin, 'count': count} 
            for asin, count in sorted(
                product_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        ]
        
        return jsonify({
            'reviews': [current_review],  # Return only one review
            'sentiment_counts': {
                'positive': total_positive,
                'negative': total_negative,
                'neutral': total_neutral,
                'total': total_reviews
            },
            'product_counts': top_products
        })
    except Exception as e:
        logger.error(f"Error in recent_reviews: {str(e)}")
        return jsonify({'error': str(e)}), 500

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