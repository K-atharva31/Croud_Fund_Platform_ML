from flask import Blueprint, app, request, jsonify, session
from app.models.user_model import UserModel
from app.models.campaign_model import CampaignModel
from app.utils.activity_logger import log_activity  # ✅ Imported logging function
from app import mongo
from bson import ObjectId
from datetime import datetime
from app.utils.decorators import role_required  # Role-based access control
from flask import request, jsonify
from werkzeug.utils import secure_filename
import os
from flask import current_app
from bson import ObjectId 

UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

creator_bp = Blueprint('creator_bp', __name__)

# ✅ 1. Creator Registration
@creator_bp.route('/register', methods=['POST'])
def register_creator():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"message": "All fields are required"}), 400

    if UserModel.find_by_email(email):
        return jsonify({"message": "User already exists"}), 400

    new_user = UserModel(name, email, password, role="creator")
    new_user.save_to_db()

    return jsonify({"message": "Creator registered successfully!"}), 201


# ✅ 2. Creator Login
@creator_bp.route('/login', methods=['POST'])
def login_creator():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    user = UserModel.find_by_email(email)
    if not user or user["role"] != "creator" or not UserModel.verify_password(user["password"], password):
        return jsonify({"message": "Invalid email or password"}), 401

    session['user_id'] = str(user['_id'])

    # ✅ Log the login activity
    log_activity(
        user_id=session['user_id'],
        action="creator_login",
        description=f"Creator '{user['name']}' logged in."
    )

    return jsonify({
        "message": "Login successful!",
        "user": {
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    })

# ✅ 3. Create Campaign
@creator_bp.route('/campaign', methods=['POST'])
@role_required('creator')
def create_campaign():
    try:
        title = request.form.get("title")
        description = request.form.get("description")
        funding_goal = request.form.get("goalAmount")
        deadline = request.form.get("endDate")
        category = request.form.get("category")
        location = request.form.get("location")
        image = request.files.get("image")
        rewards = request.form.get("rewards", [])

        deadline = datetime.strptime(deadline, '%Y-%m-%d')
        creator_id = session.get("user_id")

        # Save Image
        image_url = ""
        if image:
            filename = secure_filename(image.filename)
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            image.save(image_path)
            image_url = f"/uploads/{filename}"

        campaign = CampaignModel(
            title=title,
            description=description,
            funding_goal=funding_goal,
            funded_amount=0,
            deadline=deadline,
            category=category,
            status="pending",
            creator_id=creator_id,
            image_url=image_url,
            rewards=rewards
        )
        campaign_id = campaign.save_to_db()

        log_activity(user_id=creator_id, action="create_campaign",
                     description=f"Campaign '{title}' created.",
                     metadata={"campaign_id": str(campaign_id)})

        return jsonify({"message": "Campaign created successfully", "campaign_id": str(campaign_id)}), 201

    except Exception as e:
        print("Campaign Creation Error:", e)
        return jsonify({"message": "Something went wrong"}), 500

# ✅ 4. View All Campaigns Created by the Logged-In Creator
@creator_bp.route('/my-campaigns', methods=['GET'])
@role_required('creator')
def get_my_campaigns():
        creator_id = session.get('user_id')
        if not creator_id:
            return jsonify({"message": "Unauthorized"}), 401

        campaigns = mongo.db.campaigns.find({"creator_id": creator_id})
        campaign_list = []

        for campaign in campaigns:
            campaign_list.append({
                "campaign_id": str(campaign["_id"]),
                "title": campaign["title"],
                "description": campaign["description"],
                "funding_goal": campaign["funding_goal"],
                "funded_amount": campaign["funded_amount"],
                "category": campaign["category"],
                "deadline": campaign["deadline"].strftime("%Y-%m-%d %H:%M:%S"),
                "status": campaign["status"],
                "image_url": campaign["image_url"],
                "rewards": campaign.get("rewards", [])
            })

        return jsonify({"campaigns": campaign_list}), 200

# ✅ Creator Logout
@creator_bp.route('/logout', methods=['POST'])
@role_required('creator')
def logout_creator():
        user_id = session.get('user_id')
        creator = mongo.db.users.find_one({"_id": ObjectId(user_id)}) if user_id else None
        session.clear()

        if user_id and creator:
            log_activity(
                user_id=user_id,
                action="creator_logout",
                description=f"Creator {creator['email']} logged out"
            )

        return jsonify({"message": "Creator logged out successfully."}), 200

#creator delete/edit campaigns
@creator_bp.route('/campaign/<campaign_id>', methods=['DELETE'])
@role_required('creator')
def delete_campaign(campaign_id):
    creator_id = session.get("user_id")
    if not creator_id:
        return jsonify({"message": "Unauthorized"}), 401

    from bson import ObjectId
    try:
        campaign = mongo.db.campaigns.find_one({"_id": ObjectId(campaign_id), "creator_id": creator_id})
        if not campaign:
            return jsonify({"message": "Campaign not found or not owned by you"}), 404

        mongo.db.campaigns.delete_one({"_id": ObjectId(campaign_id)})

        # Optional: delete image file
        image_path = campaign.get("image_url", "").replace("/uploads/", "static/uploads/")
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

        return jsonify({"message": "Campaign deleted successfully"})
    except Exception as e:
        print("❌ Delete Error:", e)
        return jsonify({"message": "Internal server error"}), 500

#edit campaign
@creator_bp.route('/campaign/<campaign_id>', methods=['PUT'])
@role_required('creator')
def update_campaign(campaign_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    campaign = mongo.db.campaigns.find_one({"_id": ObjectId(campaign_id)})
    if not campaign:
        return jsonify({"message": "Campaign not found"}), 404

    if str(campaign["creator_id"]) != str(user_id):
        return jsonify({"message": "Permission denied"}), 403

    # ✅ Get updated fields
    title = request.form.get('title')
    description = request.form.get('description')
    funding_goal = request.form.get('goalAmount')
    category = request.form.get('category')
    location = request.form.get('location')
    deadline = request.form.get('endDate')

    updates = {
        "title": title,
        "description": description,
        "funding_goal": int(funding_goal),
        "category": category,
        "location": location,
        "deadline": datetime.strptime(deadline, '%Y-%m-%d'),
        "updated_at": datetime.utcnow()
    }

    # ✅ Optional image upload
    if 'image' in request.files:
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            image.save(filepath)
            updates["image_url"] = f"/{filepath}"  # Public URL

    # ✅ Perform update
    mongo.db.campaigns.update_one(
        {"_id": ObjectId(campaign_id)},
        {"$set": updates}
    )

    return jsonify({"message": "Campaign updated successfully."}), 200



# ✅ VIEW INVESTMENTS
@creator_bp.route('/investments/<campaign_id>', methods=['GET'])
@role_required('creator')
def get_campaign_investments(campaign_id):
    user_id = session.get('user_id')

    try:
        campaign = mongo.db.campaigns.find_one({"_id": ObjectId(campaign_id)})
        if not campaign or str(campaign.get("creator_id")) != str(user_id):
            return jsonify({"message": "Access denied: You are not the owner of this campaign."}), 403

        # ✅ Use ObjectId for matching campaign_id
        pipeline = [
            {"$match": {"campaign_id": ObjectId(campaign_id)}},
            {"$group": {
                "_id": "$investor_id",
                "total_investment": {"$sum": "$investment_amount"}
            }},
            {"$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "_id",
                "as": "investor"
            }},
            {"$unwind": "$investor"},
            {"$project": {
                "investor_name": "$investor.name",
                "total_investment": 1
            }}
        ]

        investors = list(mongo.db.investments.aggregate(pipeline))
        return jsonify({"investors": investors}), 200

    except Exception as e:
        print("Error in get_campaign_investments:", e)
        return jsonify({"message": "Internal Server Error"}), 500


@creator_bp.route('/campaign/<campaign_id>', methods=['GET'])
@role_required('creator')
def get_campaign_by_id(campaign_id):
    user_id = session.get("user_id")
    campaign = mongo.db.campaigns.find_one({"_id": ObjectId(campaign_id)})

    if not campaign:
        return jsonify({"message": "Campaign not found"}), 404
    if str(campaign["creator_id"]) != str(user_id):
        return jsonify({"message": "Unauthorized"}), 403

    campaign["_id"] = str(campaign["_id"])
    campaign["creator_id"] = str(campaign["creator_id"])
    campaign["deadline"] = campaign["deadline"].strftime('%Y-%m-%d')  # for <input type="date">

    return jsonify({"campaign": campaign}), 200

