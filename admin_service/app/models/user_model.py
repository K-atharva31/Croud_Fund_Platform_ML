# app/models/user_model.py
from app import mongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

class UserModel:
    @staticmethod
    def find_by_email(email):
        return mongo.db.users.find_one({"email": email})

    @staticmethod
    def find_by_id(user_id):
        try:
            return mongo.db.users.find_one({"_id": ObjectId(user_id)})
        except:
            return None

    @staticmethod
    def create_user(name, email, password, role="admin"):
        hashed = generate_password_hash(password)
        doc = {
            "name": name,
            "email": email,
            "password": hashed,
            "role": role,
            "status": "active"
        }
        return mongo.db.users.insert_one(doc)

    @staticmethod
    def verify_password(stored_hash, password):
        return check_password_hash(stored_hash, password)
