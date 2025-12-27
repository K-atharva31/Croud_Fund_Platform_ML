# app/routes/dashboard_routes.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from app import mongo

dashboard_bp = Blueprint("dashboard_bp", __name__, url_prefix="/admin/dashboard")

def clean_mongo_doc(doc):
    """Convert MongoDB ObjectId to string recursively for JSON safety."""
    if isinstance(doc, list):
        return [clean_mongo_doc(i) for i in doc]
    if isinstance(doc, dict):
        return {k: clean_mongo_doc(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc


# --- 1️⃣ Get all campaigns ---
@dashboard_bp.route("/campaigns", methods=["GET"])
@jwt_required()
def get_campaigns():
    campaigns = list(mongo.db.campaigns.find({}))
    for c in campaigns:
        fraud_alert = mongo.db.fraud_alerts.find_one({"campaign_id": str(c["_id"])})
        c["fraud_status"] = fraud_alert["label"] if fraud_alert else "not_scanned"
        c["_id"] = str(c["_id"])
    return jsonify(campaigns), 200


# --- 2️⃣ Get all fraud alerts ---
@dashboard_bp.route("/fraud/alerts", methods=["GET"])
@jwt_required()
def get_all_alerts():
    alerts = list(mongo.db.fraud_alerts.find({}).sort("timestamp", -1))
    return jsonify(clean_mongo_doc(alerts)), 200


# --- 3️⃣ Get details for one alert ---
@dashboard_bp.route("/fraud/alert/<alert_id>", methods=["GET"])
@jwt_required()
def get_alert_details(alert_id):
    alert = mongo.db.fraud_alerts.find_one({"_id": ObjectId(alert_id)})
    if not alert:
        return jsonify({"message": "Alert not found"}), 404
    return jsonify(clean_mongo_doc(alert)), 200


# --- 4️⃣ Update alert status (e.g., resolved, under_review) ---
@dashboard_bp.route("/fraud/alert/<alert_id>/status", methods=["PUT"])
@jwt_required()
def update_alert_status(alert_id):
    new_status = request.json.get("status")
    if new_status not in ["pending", "resolved", "under_review"]:
        return jsonify({"message": "Invalid status"}), 400

    result = mongo.db.fraud_alerts.update_one(
        {"_id": ObjectId(alert_id)},
        {"$set": {"status": new_status}}
    )
    if result.modified_count:
        return jsonify({"message": f"Status updated to '{new_status}'"}), 200
    return jsonify({"message": "No change"}), 200


# --- 5️⃣ Get all admins and users ---
@dashboard_bp.route("/users", methods=["GET"])
@jwt_required()
def get_all_users():
    users = list(mongo.db.users.find({}, {"password": 0}))
    return jsonify(clean_mongo_doc(users)), 200
