import os
import sys
from dotenv import load_dotenv
from pathlib import Path
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId

load_dotenv()
# Get environment variables
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Handle missing credentials gracefully
if not MONGODB_USERNAME or not MONGODB_PASSWORD:
    print("⚠️ Warning: MongoDB credentials not found in environment variables")
    CLIENT_URI = None
else:
    CLIENT_URI = f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@infostore.plsto4y.mongodb.net/?appName=infoStore"

# Initialize MongoDB connection
mongo_client = None
scheduled_interviews = None
interview_results = None

if CLIENT_URI:
    try:
        mongo_client = MongoClient(CLIENT_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        mongo_client.admin.command('ping')
        db = mongo_client[DB_NAME]
        scheduled_interviews = db["scheduled_interviews"]
        interview_results = db["interview_results"]
        print("✅ MongoDB connected successfully")
    except Exception as e:
        print(f"MongoDB connection error: {e}")
        print("⚠️ Continuing without MongoDB. Data will not be persisted.")
        mongo_client = None
        scheduled_interviews = None
        interview_results = None


def save_scheduled_interview(data: dict):
    """Save interview scheduling data to MongoDB"""
    try:
        if scheduled_interviews is None:
            print("❌ MongoDB not connected")
            return None
        
        document = {
            "interview_id": data.get("interview_id"),
            "candidate_name": data.get("candidate_name"),
            "candidate_email": data.get("candidate_email"),
            "job_description": data.get("job_description"),
            "interview_link": data.get("interview_link"),
            "start_time": data.get("start_time"),
            "end_time": data.get("end_time"),

            # ✅ ADD THESE
            "interview_status": "scheduled",  # scheduled | started | completed | expired
            "started_at": None,

            "scheduled_at": data.get("scheduled_at"),
            "created_at": datetime.utcnow()
        }


        result = scheduled_interviews.insert_one(document=document)
        print(f"✅ Interview saved to MongoDB: {result.inserted_id}")
        return str(result.inserted_id)
    
    except Exception as e:
        print(f"❌ Error saving to MongoDB: {e}")
        return None


def get_interview_by_id(interview_id: str):
    """Retrieve interview data from MongoDB"""
    try:
        if scheduled_interviews is None:
            print("❌ MongoDB not connected")
            return None
        
        interview = scheduled_interviews.find_one({"interview_id": interview_id})
        
        if interview:
            print(f"✅ Found interview in MongoDB: {interview_id}")
            return interview
        else:
            print(f"❌ Interview not found: {interview_id}")
            return None
    
    except Exception as e:
        print(f"❌ Error retrieving from MongoDB: {e}")
        return None


def save_interview_result(interview_data: dict):
    """Save final interview Q&A + evaluation to MongoDB"""
    try:
        if interview_results is None:
            print("❌ MongoDB not connected")
            return None
        
        document = {
            "interview_id": interview_data.get("interview_id"),
            "timestamp": interview_data.get("timestamp"),
            "qna": interview_data.get("qna"),
            "evaluation": interview_data.get("evaluation"),
            "video_link": interview_data.get("video_link"),
            "created_at": datetime.utcnow()
        }

        result = interview_results.insert_one(document=document)
        print(f"✅ Interview result saved to MongoDB: {result.inserted_id}")
        return str(result.inserted_id)
    
    except Exception as e:
        print(f"❌ Error saving result to MongoDB: {e}")
        return None


def get_all_interviews():
    """Get all scheduled interviews"""
    try:
        if scheduled_interviews is None:
            return []
        
        interviews = list(scheduled_interviews.find({}))
        return interviews
    
    except Exception as e:
        print(f"❌ Error fetching interviews: {e}")
        return []