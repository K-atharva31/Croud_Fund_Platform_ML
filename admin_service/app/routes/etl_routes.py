from flask import Blueprint, jsonify, request
from app import mongo
from datetime import datetime
import csv
import io

etl_bp = Blueprint("etl_bp", __name__, url_prefix="/admin/etl")

# --- Extract ---
@etl_bp.route("/extract", methods=["GET"])
def extract_data():
    users = list(mongo.db.users.find({}, {"password": 0}))  # hide password
    campaigns = list(mongo.db.campaigns.find({}))
    return jsonify({
        "users_count": len(users),
        "campaigns_count": len(campaigns),
        "users_sample": users[:3],
        "campaigns_sample": campaigns[:3]
    }), 200


# --- Transform ---
@etl_bp.route("/transform", methods=["POST"])
def transform_data():
    data = request.get_json()
    if not data or "field" not in data:
        return jsonify({"error": "Missing transformation field"}), 400

    field = data["field"]
    collection = mongo.db.campaigns

    pipeline = [
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    results = list(collection.aggregate(pipeline))
    return jsonify({"transformed": results}), 200


# --- Load / Export ---
@etl_bp.route("/export", methods=["GET"])
def export_to_csv():
    users = list(mongo.db.users.find({}, {"password": 0, "_id": 0}))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=users[0].keys() if users else [])
    writer.writeheader()
    writer.writerows(users)

    return (
        output.getvalue(),
        200,
        {
            "Content-Type": "text/csv",
            "Content-Disposition": f"attachment; filename=users_export_{datetime.now().date()}.csv",
        },
    )
