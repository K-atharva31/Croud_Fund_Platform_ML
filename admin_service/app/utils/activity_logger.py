# app/utils/activity_logger.py
from app import mongo
from datetime import datetime
from bson import ObjectId

def log_activity(user_email, action, description, metadata=None):
    """
    Stores an activity log entry in the MongoDB 'activity_log' collection.
    """
    try:
        entry = {
            "user_email": user_email,
            "action": action,
            "description": description,
            "timestamp": datetime.utcnow(),
            "metadata": metadata or {}
        }
        mongo.db.activity_log.insert_one(entry)
    except Exception as e:
        print(f"⚠️ Failed to log activity: {e}")
