from pymongo import MongoClient
import json
from datetime import datetime

def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def view_database():
    # Connect to MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client.amazon_reviews
    collection = db.reviews

    # Get total count
    total_docs = collection.count_documents({})
    print(f"\nTotal documents in database: {total_docs}")

    # Get sentiment distribution
    sentiments = collection.aggregate([
        {"$group": {"_id": "$predicted_sentiment", "count": {"$sum": 1}}}
    ])
    print("\nSentiment distribution:")
    for sentiment in sentiments:
        print(f"{sentiment['_id']}: {sentiment['count']}")

    # Show sample documents
    print("\nSample documents:")
    for doc in collection.find().limit(3):
        print("\nDocument:")
        print(json.dumps(doc, indent=2, default=json_serial))

if __name__ == "__main__":
    view_database() 