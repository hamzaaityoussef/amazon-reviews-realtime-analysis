import json
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
import time

# MongoDB configuration
MONGO_URI = "mongodb://mongodb:27017/"
DB_NAME = "amazon_reviews"
COLLECTION_NAME = "reviews"
DATA_FILE = "data/combined_data.json"

def connect_to_mongo():
    """Establish connection to MongoDB"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print("✅ Connected to MongoDB successfully")
        return collection
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        raise

def load_data_to_mongo(collection):
    """Load data from JSON file to MongoDB"""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            # Read all lines and parse JSON
            data = [json.loads(line) for line in f]
            
            # Insert in batches for better performance
            batch_size = 100
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                try:
                    result = collection.insert_many(batch, ordered=False)
                    print(f"✅ Inserted {len(result.inserted_ids)} documents")
                except BulkWriteError as bwe:
                    print(f"⚠️  Some duplicates skipped: {bwe.details['nInserted']} inserted")
                
                # Small delay to not overwhelm the server
                time.sleep(0.1)
                
        print("🎉 All data loaded successfully!")
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        raise

if __name__ == "__main__":
    print("Starting MongoDB data loader...")
    collection = connect_to_mongo()
    load_data_to_mongo(collection)