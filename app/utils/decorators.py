from functools import wraps
from flask import request, jsonify, session
from app.models.user_model import UserModel
from bson import ObjectId  # Add this import to fix the error
from app import mongo
# Update role_required decorator in decorators.py
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if the user is logged in
            if 'user_id' not in session:
                return jsonify({"message": "Unauthorized. Please login."}), 401

            user_id = session['user_id']
            user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
            
            if not user or user["role"] != role:
                return jsonify({"message": f"Access denied, insufficient permissions."}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
