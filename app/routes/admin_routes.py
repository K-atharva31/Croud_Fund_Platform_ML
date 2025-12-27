from datetime import datetime
from flask import Blueprint, request, jsonify, session
from app.models.user_model import UserModel
from app import mongo
from bson.errors import InvalidId
from bson import ObjectId
from app.utils.decorators import role_required
from app.utils.activity_logger import log_activity  # 🔥 NEW

admin_bp = Blueprint('admin_bp', __name__)

MAIN_ADMIN_EMAIL = "21bce036@nirmauni.ac.in"

# Register New Admin (Only by Main Admin)
@admin_bp.route('/register', methods=['POST'])
@role_required('admin')
def register_admin():
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can create new admins."}), 403

    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"message": "All fields are required"}), 400

    if UserModel.find_by_email(email):
        return jsonify({"message": "User already exists"}), 400

    new_user = UserModel(name, email, password, role="admin")
    new_user.save_to_db()

    log_activity(
        user_id=session['user_id'],
        action="create_admin",
        description=f"Main admin created a new admin: {email}",
        metadata={"new_admin_email": email}
    )

    return jsonify({"message": "Admin created successfully!"}), 201

# GET route to fetch all admins (only main admin access)
@admin_bp.route('/all-admins', methods=['GET'])
@role_required('admin')
def get_all_admins():
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can view admin list."}), 403

    admins = mongo.db.users.find({"role": "admin"})
    admin_list = []
    for admin in admins:
        admin_list.append({
            "_id": str(admin["_id"]),
            "name": admin["name"],
            "email": admin["email"],
            "role": admin["role"],
            "status": admin.get("status", "active")
        })

    return jsonify({"admins": admin_list}), 200

# Toggle Admin Status (Main Admin Only)
@admin_bp.route('/toggle-status/<admin_id>', methods=['PUT'])
@role_required('admin')
def toggle_admin_status(admin_id):
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can update status."}), 403

    admin = mongo.db.users.find_one({"_id": ObjectId(admin_id), "role": "admin"})
    if not admin:
        return jsonify({"message": "Admin not found"}), 404

    new_status = "disabled" if admin.get("status", "active") == "active" else "active"
    mongo.db.users.update_one({"_id": ObjectId(admin_id)}, {"$set": {"status": new_status}})

    log_activity(
        user_id=session['user_id'],
        action="toggle_admin_status",
        description=f"Main admin changed status of {admin['email']} to {new_status}",
        metadata={"admin_id": admin_id, "new_status": new_status}
    )

    return jsonify({"message": f"Admin {new_status} successfully."}), 200

# Delete Admin
@admin_bp.route('/delete/<admin_id>', methods=['DELETE'])
@role_required('admin')
def delete_admin(admin_id):
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can delete an admin."}), 403

    admin = mongo.db.users.find_one({"_id": ObjectId(admin_id), "role": "admin"})
    if not admin:
        return jsonify({"message": "Admin not found"}), 404

    if admin["email"] == MAIN_ADMIN_EMAIL:
        return jsonify({"message": "You cannot delete yourself (main admin)."}), 403

    mongo.db.users.delete_one({"_id": ObjectId(admin_id)})

    log_activity(
        user_id=session['user_id'],
        action="delete_admin",
        description=f"Main admin deleted admin: {admin['email']}",
        metadata={"deleted_admin_id": admin_id}
    )

    return jsonify({"message": "Admin deleted successfully."}), 200



# Admin Login
@admin_bp.route('/login', methods=['POST'])
def login_admin():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    user = UserModel.find_by_email(email)
    if not user or user["role"] != "admin" or not UserModel.verify_password(user["password"], password):
        return jsonify({"message": "Invalid email or password"}), 401

    session['user_id'] = str(user['_id'])
    session['user_email'] = user['email']

    log_activity(
        user_id=session['user_id'],
        action="admin_login",
        description=f"Admin {email} logged in"
    )

    return jsonify({
        "message": "Login successful!",
        "user": {
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    })

# View All Campaigns
@admin_bp.route('/campaigns', methods=['GET'])
@role_required('admin')
def view_all_campaigns():
    campaigns = mongo.db.campaigns.find({})
    campaign_list = []

    for campaign in campaigns:
        creator_name = "Unknown"
        try:
            creator_id = campaign.get("creator_id", "")
            if ObjectId.is_valid(creator_id):
                creator = mongo.db.users.find_one({"_id": ObjectId(creator_id)})
                if creator:
                    creator_name = creator.get("name", "Unknown")
        except InvalidId:
            pass

        campaign_list.append({
            "campaign_id": str(campaign["_id"]),
            "title": campaign["title"],
            "creator_name": creator_name,
            "funding_goal": campaign["funding_goal"],
            "funded_amount": campaign["funded_amount"],
            "category": campaign["category"],
            "status": campaign["status"],
            "created_at": campaign["created_at"],
            "image_url": campaign["image_url"],
            "deadline": campaign["deadline"].isoformat() if "deadline" in campaign else ""
        })

    return jsonify({"campaigns": campaign_list}), 200

# Approve / Reject Campaign
@admin_bp.route('/campaigns/<campaign_id>', methods=['PUT'])
@role_required('admin')
def approve_or_reject_campaign(campaign_id):
    data = request.get_json()
    status = data.get("status")

    if status not in ["approved", "rejected"]:
        return jsonify({"message": "Invalid status"}), 400

    result = mongo.db.campaigns.update_one(
        {"_id": ObjectId(campaign_id)},
        {"$set": {"status": status}}
    )

    if result.matched_count == 0:
        return jsonify({"message": "Campaign not found"}), 404

    log_activity(
        user_id=session['user_id'],
        action=f"campaign_{status}",
        description=f"Campaign {campaign_id} was {status}"
    )

    return jsonify({"message": "Campaign status updated successfully!"}), 200

# View All Users
@admin_bp.route('/all-users', methods=['GET'])
@role_required('admin')
def view_all_users():   
    users = mongo.db.users.find({})
    user_list = [{
        "name": user["name"],
        "email": user["email"],
        "role": user["role"]
    } for user in users]

    return jsonify({"users": user_list}), 200


# View All Investments
@admin_bp.route('/all-investments', methods=['GET'])
@role_required('admin')
def view_all_investments():
    investments = mongo.db.investments.find({})
    investment_list = []

    for investment in investments:
        investor = mongo.db.users.find_one({"_id": ObjectId(investment["investor_id"])})
        investor_name = investor["name"] if investor else "Unknown"

        campaign = mongo.db.campaigns.find_one({"_id": ObjectId(investment["campaign_id"])})
        campaign_title = campaign["title"] if campaign else "Unknown"

        investment_list.append({
            "investor_name": investor_name,
            "campaign_title": campaign_title,
            "amount": investment["investment_amount"],
            "date": investment.get("investment_date", datetime.utcnow()).isoformat()
        })

    return jsonify({"investments": investment_list}), 200


# 🔍 Activity Log Viewer (Main Admin Only)
@admin_bp.route('/activity', methods=['GET'])
@role_required('admin')
def view_activity_log():
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can view activity logs."}), 403

    logs = mongo.db.activity_log.find().sort("timestamp", -1)
    activity_list = []

    for log in logs:
        activity_list.append({
            "action": log.get("action"),
            "performed_by": str(log.get("user_id")),
            "timestamp": log["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "description": log.get("description"),
            "metadata": log.get("metadata", {})
        })

    return jsonify({"activities": activity_list}), 200

# ✅ Delete User (Only by Main Admin)
@admin_bp.route('/delete-user/<user_id>', methods=['DELETE'])
@role_required('admin')
def delete_user(user_id):
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can delete users."}), 403

    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return jsonify({"message": "Invalid user ID."}), 400

    user_to_delete = mongo.db.users.find_one({"_id": obj_id})
    if not user_to_delete:
        return jsonify({"message": "User not found."}), 404

    if user_to_delete["email"] == MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Main admin cannot be deleted."}), 403

    mongo.db.users.delete_one({"_id": obj_id})

    log_activity(
        user_id=session['user_id'],
        action="user_deleted",
        description=f"Deleted user: {user_to_delete['email']}",
        metadata={"deleted_user_id": user_id, "role": user_to_delete.get("role")}
    )

    return jsonify({"message": f"User {user_to_delete['email']} deleted successfully."}), 200

# Admin Logout
@admin_bp.route('/logout', methods=['POST'])
@role_required('admin')
def logout_admin():
    user_id = session.get('user_id')
    user_email = session.get('user_email')
    
    if user_id:
        log_activity(
            user_id=user_id,
            action="admin_logout",
            description=f"Admin {user_email} logged out"
        )

    session.clear()
    return jsonify({"message": "Admin logged out successfully."}), 200