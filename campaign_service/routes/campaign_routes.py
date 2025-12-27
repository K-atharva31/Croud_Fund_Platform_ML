from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from extensions import mongo
from datetime import datetime
import os

campaign_bp = Blueprint("campaign_bp", __name__)

@campaign_bp.route("/campaign", methods=["POST"])
def create_campaign():
    try:
        title = request.form.get("title")
        description = request.form.get("description")
        funding_goal = float(request.form.get("goalAmount", 0))
        deadline = request.form.get("endDate")
        category = request.form.get("category")
        location = request.form.get("location")
        image = request.files.get("image")

        deadline = datetime.strptime(deadline, '%Y-%m-%d')
        image_url = ""
        if image:
            filename = secure_filename(image.filename)
            filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            image.save(filepath)
            image_url = f"/uploads/{filename}"

        mongo.db.campaigns.insert_one({
            "title": title,
            "description": description,
            "funding_goal": funding_goal,
            "funded_amount": 0,
            "deadline": deadline,
            "category": category,
            "location": location,
            "status": "active",
            "image_url": image_url,
        })

        return jsonify({"message": "Campaign created successfully"}), 201
    except Exception as e:
        print("❌ Error creating campaign:", e)
        return jsonify({"message": "Internal server error"}), 500


@campaign_bp.route("/campaigns", methods=["GET"])
def get_campaigns():
    try:
        campaigns = list(mongo.db.campaigns.find())
        for c in campaigns:
            c["_id"] = str(c["_id"])
        return jsonify(campaigns), 200
    except Exception as e:
        print("❌ Error fetching campaigns:", e)
        return jsonify({"message": "Internal server error"}), 500
