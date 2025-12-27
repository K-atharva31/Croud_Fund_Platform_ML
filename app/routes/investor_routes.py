from flask import Blueprint, request, jsonify, session
from app.models.user_model import UserModel
from app.models.campaign_model import CampaignModel
from app import mongo
from bson import ObjectId
from datetime import datetime
from app.utils.decorators import role_required
from app.utils.activity_logger import log_activity  # ✅ NEW
import razorpay
import os

RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))



investor_bp = Blueprint('investor_bp', __name__)

# Investor Registration
@investor_bp.route('/register', methods=['POST'])
def register_investor():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"message": "All fields are required"}), 400

    if UserModel.find_by_email(email):
        return jsonify({"message": "User already exists"}), 400

    new_user = UserModel(name, email, password, role="investor")
    new_user.save_to_db()

    user = UserModel.find_by_email(email)
    log_activity(user_id=str(user["_id"]), action="user_registered", description=f"Investor {name} registered")

    return jsonify({"message": "Investor registered successfully!"}), 201

# Investor Login
@investor_bp.route('/login', methods=['POST'])
def login_investor():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    user = UserModel.find_by_email(email)
    if not user:
        return jsonify({"message": "User not found"}), 404

    if user["role"] != "investor" or not UserModel.verify_password(user["password"], password):
        return jsonify({"message": "Invalid email or password"}), 401

    session['user_id'] = str(user['_id'])

    log_activity(user_id=session['user_id'], action="login", description="Investor logged in")

    return jsonify({
        "message": "Login successful!",
        "user": {
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    })

# Investor Invest in a Campaign
@investor_bp.route('/invest', methods=['POST'])
@role_required('investor')
def invest_in_campaign():
    try:
        data = request.get_json()
        campaign_id = data.get("campaign_id")
        investment_amount = data.get("investment_amount")
        investor_id = session.get('user_id')

        if not campaign_id or not investment_amount or not investor_id:
            return jsonify({"message": "Campaign ID, investment amount, and investor ID are required"}), 400

        try:
            investment_amount = int(investment_amount)
        except (TypeError, ValueError):
            return jsonify({"message": "Invalid investment amount"}), 400

        if investment_amount <= 0:
            return jsonify({"message": "Investment amount must be greater than 0"}), 400

        campaign = CampaignModel.find_by_id(campaign_id)
        if not campaign or campaign.status == 'completed':
            return jsonify({"message": "Campaign not found or already completed"}), 404

        # Convert both funded_amount and funding_goal to integers safely
        try:
            campaign.funded_amount = int(campaign.funded_amount)
            campaign.funding_goal = int(campaign.funding_goal)
        except Exception:
            return jsonify({"message": "Invalid campaign funding values."}), 500

        if campaign.funded_amount >= campaign.funding_goal:
            return jsonify({"message": "Campaign funding goal has been met. No further investments allowed."}), 403

        # Update funded amount
        campaign.funded_amount += investment_amount
        CampaignModel.update_campaign(campaign_id, {"funded_amount": campaign.funded_amount})

        if campaign.funded_amount >= campaign.funding_goal:
            CampaignModel.update_campaign(campaign_id, {"status": "completed"})

        # Save investment
        investment = {
            "campaign_id": ObjectId(campaign_id),
            "investor_id": ObjectId(investor_id),
            "investment_amount": investment_amount,
            "investment_date": datetime.utcnow()
        }
        mongo.db.investments.insert_one(investment)

        # Log activity
        log_activity(
            user_id=investor_id,
            action="investment_made",
            description=f"Invested ₹{investment_amount} in campaign {campaign_id}",
            metadata={"amount": investment_amount, "campaign_id": campaign_id}
        )

        return jsonify({"message": "Investment successful!"}), 200

    except Exception as e:
        print(f"Error in invest route: {str(e)}")
        return jsonify({"message": "Internal Server Error"}), 500


# View All Approved or Completed Campaigns
@investor_bp.route('/campaigns', methods=['GET'])
@role_required('investor')
def view_campaigns():
    campaigns = mongo.db.campaigns.find({"status": {"$in": ["active","approved", "completed"]}})
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
            "rewards": campaign["rewards"],
            "status": campaign["status"],
            "image_url": campaign["image_url"]
        })

    return jsonify({"campaigns": campaign_list}), 200

# Investor View Their Investments
@investor_bp.route('/my-investments', methods=['GET'])
@role_required('investor')
def view_my_investments():
    investor_id = session.get('user_id')

    pipeline = [
        {"$match": {"investor_id": ObjectId(investor_id)}},
        {"$group": {
            "_id": "$campaign_id",
            "total_amount": {"$sum": "$investment_amount"},
            "last_date": {"$max": "$investment_date"}
        }},
        {"$lookup": {
            "from": "campaigns",
            "localField": "_id",
            "foreignField": "_id",
            "as": "campaign_info"
        }},
        {"$unwind": "$campaign_info"},
        {"$project": {
            "campaign_id": {"$toString": "$_id"},
            "campaign_title": "$campaign_info.title",
            "campaign_status": "$campaign_info.status",
            "investment_amount": "$total_amount",
            "investment_date": {
                "$dateToString": {
                    "format": "%Y-%m-%d %H:%M:%S",
                    "date": "$last_date"
                }
            }
        }}
    ]

    results = list(mongo.db.investments.aggregate(pipeline))
    return jsonify({"investments": results}), 200

# Investor Logout
# Investor Logout
@investor_bp.route('/logout', methods=['POST'])
@role_required('investor')
def logout_investor():
    user_id = session.get('user_id')
    
    if user_id:
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        email = user["email"] if user else "unknown"

        log_activity(
            user_id=user_id,
            action="investor_logout",
            description=f"Investor {email} logged out"
        )

    session.clear()
    return jsonify({"message": "Investor logged out successfully."}), 200

#RAZERPAY
@investor_bp.route('/create-razorpay-order', methods=['POST'])
@role_required('investor')
def create_razorpay_order():
    try:
        data = request.get_json()
        amount = int(data['amount']) * 100  # Convert ₹ to paise
        currency = "INR"

        order = razorpay_client.order.create({
            "amount": amount,
            "currency": currency,
            "payment_capture": 1
        })

        return jsonify({
            "order_id": order['id'],
            "amount": amount,
            "currency": currency,
            "razorpay_key": RAZORPAY_KEY_ID
        }), 200

    except Exception as e:
        print(f"Error creating Razorpay order: {str(e)}")
        return jsonify({"message": "Error creating payment order"}), 500
