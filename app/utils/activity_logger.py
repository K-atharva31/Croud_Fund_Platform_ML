from app import mongo
from datetime import datetime
from bson import ObjectId

def log_activity(user_id, action, description, metadata=None):
    try:
        if isinstance(user_id, str) and ObjectId.is_valid(user_id):
            user_id = ObjectId(user_id)  # Only convert if it's a valid ObjectId

        log_entry = {
            "user_id": user_id,  # Could be email or ObjectId
            "action": action,
            "description": description,
            "timestamp": datetime.utcnow(),
            "metadata": metadata or {}
        }

        mongo.db.activity_log.insert_one(log_entry)

    except Exception as e:
        print(f"⚠️ Failed to log activity: {str(e)}")