import csv
from io import StringIO
from flask import Blueprint, Response, jsonify, session, current_app
from app import mongo
from bson import ObjectId
from datetime import datetime
from pymongo import MongoClient
from app.utils.decorators import role_required
from app.utils.activity_logger import log_activity

etl_bp = Blueprint('etl_bp', __name__)

# Fixed Main Admin Email
MAIN_ADMIN_EMAIL = "21bce036@nirmauni.ac.in"

# ✅ ETL Migrate Route (Main Admin only)
@etl_bp.route('/migrate', methods=['POST'])
@role_required('admin')
def migrate_data():
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can perform this action."}), 403

    try:
        cloud_client = MongoClient(current_app.config["MONGO_ATLAS_URI"], tls=True, tlsAllowInvalidCertificates=True)
        cloud_db = cloud_client['CrowdfundingCloudDB']

        collections = ["campaigns", "users", "investments"]
        migration_log = {
            "timestamp": datetime.utcnow(),
            "status": "in-progress",
            "collections": {}
        }

        for collection in collections:
            local_data = list(mongo.db[collection].find({}))
            if not local_data:
                migration_log["collections"][collection] = {"migrated_count": 0}
                continue

            for doc in local_data:
                doc["_id"] = str(doc["_id"])

            cloud_db[collection].insert_many(local_data)
            migration_log["collections"][collection] = {"migrated_count": len(local_data)}

        migration_log["status"] = "completed"
        mongo.db.migration_logs.insert_one(migration_log)
        cloud_db['migration_logs'].insert_one(migration_log)

        # ✅ Log activity (corrected order)
        log_activity(
            user_id=session['user_id'],
            action="etl_migrated",
            description="Data migrated from local to cloud DB"
        )

        return jsonify({"message": "Migration completed successfully.", "log": migration_log}), 200

    except Exception as e:
        import traceback
        print("🔴 ETL MIGRATION ERROR:", traceback.format_exc())
        return jsonify({"message": "Migration failed.", "error": str(e)}), 500


# ✅ Preview Route (Any admin)
@etl_bp.route('/preview', methods=['GET'])
@role_required('admin')
def preview_data():
    try:
        preview = {}
        collections = ["campaigns", "users", "investments"]

        for collection in collections:
            data = list(mongo.db[collection].find({}).limit(5))
            for record in data:
                record["_id"] = str(record["_id"])
            preview[collection] = data

        return jsonify({"message": "Preview fetched successfully.", "data": preview}), 200

    except Exception as e:
        return jsonify({"message": "Failed to fetch preview data.", "error": str(e)}), 500

# ✅ Delete Local Data (Main Admin only)
@etl_bp.route('/delete-local', methods=['DELETE'])
@role_required('admin')
def delete_local_data():
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({"message": "Only main admin can delete local data."}), 403

    try:
        collections = ["campaigns", "investments"]
        deletion_log = {}

        for collection in collections:
            result = mongo.db[collection].delete_many({})
            deletion_log[collection] = result.deleted_count

        result = mongo.db.users.delete_many({"email": {"$ne": MAIN_ADMIN_EMAIL}})
        deletion_log["users"] = result.deleted_count

        # ✅ Log activity (corrected order)
        log_activity(
            user_id=session['user_id'],
            action="local_data_deleted",
            description="Local DB (except main admin) wiped"
        )

        return jsonify({"message": "Local data (except main admin) deleted successfully.", "deletion_log": deletion_log}), 200

    except Exception as e:
        return jsonify({"message": "Failed to delete local data.", "error": str(e)}), 500
    
#Export Campaigns
@etl_bp.route('/export-campaigns', methods=['GET'])
@role_required('admin')
def export_campaigns():
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({'error': 'Unauthorized'}), 403

    campaigns = mongo.db.campaigns.find()
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Title', 'Description', 'Funding Goal', 'Funded Amount',
        'Deadline', 'Category', 'Status', 'Creator ID', 'Created At'
    ])

    # Write each campaign
    for c in campaigns:
        writer.writerow([
            c.get('title', ''),
            c.get('description', ''),
            c.get('funding_goal', ''),
            c.get('funded_amount', ''),
            c.get('deadline', ''),
            c.get('category', ''),
            c.get('status', ''),
            c.get('creator_id', ''),
            c.get('created_at', '')
        ])

    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=all_campaigns.csv"})


#Export Investments
@etl_bp.route('/export-investments', methods=['GET'])
@role_required('admin')
def export_investments():
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({'error': 'Unauthorized'}), 403

    investments = mongo.db.investments.find()
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Campaign ID', 'Investor ID', 'Amount', 'Date'
    ])

    # Data
    for inv in investments:
        writer.writerow([
            inv.get('campaign_id', ''),
            inv.get('investor_id', ''),
            inv.get('amount', ''),
            inv.get('created_at', '')
        ])

    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=all_investments.csv"})


#Export Logs
@etl_bp.route('/export-logs', methods=['GET'])
@role_required('admin')
def export_logs():
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({'error': 'Unauthorized'}), 403

    logs = mongo.db.activity_logs.find()
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'User ID', 'Action', 'Description', 'Timestamp', 'Metadata'
    ])

    for log in logs:
        writer.writerow([
            log.get('user_id', ''),
            log.get('action', ''),
            log.get('description', ''),
            log.get('timestamp', ''),
            str(log.get('metadata', ''))
        ])

    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=activity_logs.csv"})

#Export Users
@etl_bp.route('/export-users', methods=['GET'])
@role_required('admin')
def export_users():
    if session.get('user_email') != MAIN_ADMIN_EMAIL:
        return jsonify({'error': 'Unauthorized'}), 403

    users = mongo.db.users.find()
    output = StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(['Name', 'Email', 'Role', 'Registered At'])

    # Data rows
    for user in users:
        writer.writerow([
            user.get('name', ''),
            user.get('email', ''),
            user.get('role', ''),
            user.get('created_at', '')
        ])

    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=all_users.csv"})
