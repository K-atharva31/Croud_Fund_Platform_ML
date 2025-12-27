from flask import Blueprint, jsonify, request
from models.user_model import UserModel

user_bp = Blueprint("user_bp", __name__)

@user_bp.route("/users", methods=["GET"])
def get_users():
    users = UserModel.get_all_users()
    return jsonify(users)

@user_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "investor")

    if UserModel.find_by_email(email):
        return jsonify({"error": "User already exists"}), 400

    user = UserModel(name, email, password, role)
    user.save_to_db()
    return jsonify({"message": "User created successfully"}), 201


@user_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user = UserModel.find_by_email(email)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not UserModel.verify_password(user["password"], password):
        return jsonify({"error": "Incorrect password"}), 401

    return jsonify({
        "message": "Login successful",
        "user_id": str(user["_id"]),
        "role": user["role"]
    }), 200


@user_bp.route("/profile/<user_id>", methods=["GET"])
def get_profile(user_id):
    from app import mongo
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        return jsonify({"error": "User not found"}), 404
    user["_id"] = str(user["_id"])
    return jsonify(user), 200


@user_bp.route("/is_main_admin/<user_id>", methods=["GET"])
def is_main_admin(user_id):
    result = UserModel.is_main_admin(user_id)
    return jsonify({"is_main_admin": result}), 200
