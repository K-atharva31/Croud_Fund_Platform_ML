from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from __init__ import mongo

class UserModel:
    MAIN_ADMIN_EMAIL = "mainadmin@crowdfund.com"  # Fixed main admin email

    def __init__(self, name, email, password, role):
        self.name = name
        self.email = email
        self.password = generate_password_hash(password)
        self.role = role

    def save_to_db(self):
        mongo.db.users.insert_one({
            "name": self.name,
            "email": self.email,
            "password": self.password,
            "role": self.role
        })

    @staticmethod
    def find_by_email(email):
        return mongo.db.users.find_one({"email": email})

    @staticmethod
    def verify_password(stored_password, input_password):
        return check_password_hash(stored_password, input_password)

    @staticmethod
    def is_main_admin(user_id):
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("email") == UserModel.MAIN_ADMIN_EMAIL and user.get("role") == "admin":
            return True
        return False