# app/routes/admin_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models.user_model import UserModel
from app.utils.activity_logger import log_activity
from app import mongo
from app.config import Config
from bson import ObjectId
from datetime import datetime
from flask import make_response
import csv
import io

def log_activity(admin_email, action, details):
    log_entry = {
        "admin": admin_email,
        "action": action,
        "details": details,
        "timestamp": datetime.utcnow()
    }
    mongo.db.admin_logs.insert_one(log_entry)

admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")
MAIN_ADMIN_EMAIL = Config.MAIN_ADMIN_EMAIL

# --- LOGIN ADMIN ---
@admin_bp.route("/login", methods=["POST"])
def login_admin():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password required"}), 400

    user = UserModel.find_by_email(email)
    if not user or user.get("role") != "admin":
        return jsonify({"message": "Invalid email or password"}), 401

    if not UserModel.verify_password(user["password"], password):
        return jsonify({"message": "Invalid email or password"}), 401

    token = create_access_token(identity=user["email"])
    log_activity(email, "login", f"Admin {email} logged in")

    return jsonify({
        "message": "Login successful",
        "access_token": token,
        "user": {
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    }), 200


# --- REGISTER ADMIN (main admin only) ---
@admin_bp.route("/register", methods=["POST"])
@jwt_required()
def register_admin():
    current_user = get_jwt_identity()
    if current_user != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can register new admins."}), 403

    data = request.get_json() or {}
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not (name and email and password):
        return jsonify({"message": "All fields required"}), 400

    if UserModel.find_by_email(email):
        return jsonify({"message": "User already exists"}), 400

    UserModel.create_user(name, email, password, "admin")
    log_activity(current_user, "create_admin", f"Created new admin {email}")

    return jsonify({"message": f"Admin {email} created successfully."}), 201


# -------- existing routes (login/register) stay above -------- #

@admin_bp.route("/all-admins", methods=["GET"])
@jwt_required()
def list_admins():
    current_user = get_jwt_identity()
    admins = list(mongo.db.users.find({"role": "admin"}))
    result = [{
        "_id": str(a["_id"]),
        "name": a["name"],
        "email": a["email"],
        "status": a.get("status", "active")
    } for a in admins]
    log_activity(current_user, "view_admins", "Viewed admin list")
    return jsonify({"admins": result}), 200


@admin_bp.route("/toggle-status/<admin_id>", methods=["PUT"])
@jwt_required()
def toggle_admin_status(admin_id):
    current_user = get_jwt_identity()
    if current_user != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can toggle status."}), 403

    admin = mongo.db.users.find_one({"_id": ObjectId(admin_id), "role": "admin"})
    if not admin:
        return jsonify({"message": "Admin not found"}), 404

    new_status = "disabled" if admin.get("status", "active") == "active" else "active"
    mongo.db.users.update_one({"_id": ObjectId(admin_id)}, {"$set": {"status": new_status}})

    log_activity(
        current_user,
        "toggle_admin_status",
        f"Changed status for {admin['email']} to {new_status}",
        {"admin_id": admin_id, "new_status": new_status}
    )
    return jsonify({"message": f"Admin {new_status} successfully."}), 200


@admin_bp.route("/delete/<admin_id>", methods=["DELETE"])
@jwt_required()
def delete_admin(admin_id):
    current_user = get_jwt_identity()
    if current_user != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can delete admins."}), 403

    admin = mongo.db.users.find_one({"_id": ObjectId(admin_id), "role": "admin"})
    if not admin:
        return jsonify({"message": "Admin not found"}), 404

    if admin["email"] == MAIN_ADMIN_EMAIL:
        return jsonify({"message": "You cannot delete yourself (main admin)."}), 403

    mongo.db.users.delete_one({"_id": ObjectId(admin_id)})

    log_activity(
        current_user,
        "delete_admin",
        f"Deleted admin {admin['email']}",
        {"deleted_admin_id": admin_id}
    )
    return jsonify({"message": "Admin deleted successfully."}), 200


# --- ADMIN DASHBOARD DATA ENDPOINTS ---

@admin_bp.route("/summary", methods=["GET"])
@jwt_required(optional=True)
def admin_summary():
    """Return live statistics for dashboard cards."""
    try:
        campaign_count = mongo.db.campaigns.count_documents({})
        active_campaigns = mongo.db.campaigns.count_documents({"status": "active"})
        user_count = mongo.db.users.count_documents({})
        total_investments = mongo.db.investments.count_documents({}) if "investments" in mongo.db.list_collection_names() else 0

        return jsonify({
            "total_campaigns": campaign_count,
            "active_campaigns": active_campaigns,
            "total_users": user_count,
            "total_investments": total_investments,
            "revenue": total_investments * 100  # placeholder
        }), 200

    except Exception as e:
        import traceback
        print("❌ ERROR in /admin/summary:\n", traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/campaigns", methods=["GET"])
@jwt_required(optional=True)
def admin_campaigns():
    """Return the 10 most recent campaigns."""
    try:
        data = list(
            mongo.db.campaigns.find({}, {"_id": 0})
            .sort("_id", -1)
            .limit(10)
        )
        return jsonify(data), 200

    except Exception as e:
        import traceback
        print("❌ ERROR in /admin/campaigns:\n", traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/users", methods=["GET"])
@jwt_required(optional=True)
def admin_users():
    """Return the 10 most recent users."""
    try:
        data = list(
            mongo.db.users.find({}, {"_id": 0, "name": 1, "email": 1, "created_at": 1})
            .sort("_id", -1)
            .limit(10)
        )
        return jsonify(data), 200

    except Exception as e:
        import traceback
        print("❌ ERROR in /admin/users:\n", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@admin_bp.route("/debug/users")
def debug_users():
    try:
        users = list(mongo.db.users.find({}, {"_id": 0, "email": 1, "role": 1, "password": 1}))
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route("/logs", methods=["GET"])
@jwt_required()
def get_logs():
    try:
        current_user = get_jwt_identity()

        # verify admin
        user = UserModel.find_by_email(current_user)
        if not user or user.get("role") != "admin":
            return jsonify({"message": "Unauthorized"}), 403

        # query params: page, per_page, q (search), action
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 20))
        except ValueError:
            page = 1
            per_page = 20

        q = request.args.get("q", "").strip()
        action_filter = request.args.get("action", "").strip()

        # build mongo filter
        mongo_filter = {}
        if action_filter:
            mongo_filter["action"] = action_filter
        if q:
            # search admin or details (case-insensitive)
            mongo_filter["$or"] = [
                {"admin": {"$regex": q, "$options": "i"}},
                {"details": {"$regex": q, "$options": "i"}}
            ]

        total = mongo.db.admin_logs.count_documents(mongo_filter)
        cursor = mongo.db.admin_logs.find(mongo_filter).sort("timestamp", -1).skip((page - 1) * per_page).limit(per_page)
        logs = list(cursor)

        # serialize results
        for log in logs:
            log["_id"] = str(log.get("_id"))
            # ensure timestamp string
            ts = log.get("timestamp")
            log["timestamp"] = str(ts) if ts is not None else ""

        return jsonify({
            "logs": logs,
            "total": total,
            "page": page,
            "per_page": per_page
        }), 200

    except Exception as e:
        return jsonify({"message": "Failed to load logs", "error": str(e)}), 500


# --- EXPORT ACTIVITY LOGS AS CSV ---
@admin_bp.route("/logs/export", methods=["GET"])
@jwt_required()
def export_logs_csv():
    try:
        current_user = get_jwt_identity()
        user = UserModel.find_by_email(current_user)
        if not user or user.get("role") != "admin":
            return jsonify({"message": "Unauthorized"}), 403

        # support same filters as /logs
        q = request.args.get("q", "").strip()
        action_filter = request.args.get("action", "").strip()

        mongo_filter = {}
        if action_filter:
            mongo_filter["action"] = action_filter
        if q:
            mongo_filter["$or"] = [
                {"admin": {"$regex": q, "$options": "i"}},
                {"details": {"$regex": q, "$options": "i"}}
            ]

        cursor = mongo.db.admin_logs.find(mongo_filter).sort("timestamp", -1)

        # build CSV in-memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["_id", "admin", "action", "details", "timestamp"])

        for log in cursor:
            _id = str(log.get("_id"))
            admin = log.get("admin", "")
            action = log.get("action", "")
            details = log.get("details", "")
            timestamp = str(log.get("timestamp", ""))
            writer.writerow([_id, admin, action, details, timestamp])

        csv_content = output.getvalue()
        output.close()

        resp = make_response(csv_content)
        resp.headers["Content-Disposition"] = "attachment; filename=admin_activity_logs.csv"
        resp.headers["Content-Type"] = "text/csv; charset=utf-8"
        return resp

    except Exception as e:
        return jsonify({"message": "Export failed", "error": str(e)}), 500
