# admin_service/app/routes/fraud_routes.py
from flask import Blueprint, jsonify, request, current_app, abort
from bson.objectid import ObjectId
import os
import traceback

from ..ml.fraud_model import FraudDetector

fraud_bp = Blueprint("fraud_routes", __name__, url_prefix="/admin/api/fraud")

# single shared detector instance (module-level)
_detector = None

def get_detector():
    global _detector
    if _detector is None:
        _detector = FraudDetector()
    return _detector

def get_mongo():
    """
    Try to obtain a pymongo client from current_app config (if preconfigured),
    otherwise create a lightweight client from env MONGO_URI.
    Expect database name in env MONGO_DB or current_app.config['MONGO_DB'].
    """
    try:
        # common pattern: current_app.extensions['pymongo'] or current_app.config
        client = current_app.config.get("MONGO_CLIENT")
        if client:
            return client
    except Exception:
        pass

    from pymongo import MongoClient
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    client = MongoClient(uri)
    return client

@fraud_bp.route("/flagged", methods=["GET"])
def list_flagged():
    """
    Query flagged campaigns from Mongo.
    Query params:
      - min_score: float (0..1) default 0.3
      - limit: int default 100
      - status: flagged/reviewed/cleared
    """
    try:
        mongo = get_mongo()
        dbname = current_app.config.get("MONGO_DB", os.environ.get("MONGO_DB", "crwdfund"))
        db = mongo[dbname]
        collection = db.get_collection("campaigns")
        min_score = float(request.args.get("min_score", 0.3))
        limit = int(request.args.get("limit", 200))
        status = request.args.get("status", None)

        query = {"fraud.score": {"$gte": min_score}}
        if status:
            query["fraud.status"] = status

        docs = list(collection.find(query).sort("fraud.score", -1).limit(limit))
        # convert ObjectId to string and reduce payload
        for d in docs:
            d["_id"] = str(d["_id"])
            # reduce features for listing
            if "fraud" in d and "features_used" in d["fraud"]:
                d["fraud"].pop("features_used", None)
        return jsonify(docs)
    except Exception as e:
        current_app.logger.error("list_flagged error: %s", e)
        current_app.logger.error(traceback.format_exc())
        abort(500, description=str(e))

@fraud_bp.route("/<campaign_id>", methods=["GET"])
def get_campaign(campaign_id):
    try:
        mongo = get_mongo()
        dbname = current_app.config.get("MONGO_DB", os.environ.get("MONGO_DB", "crwdfund"))
        db = mongo[dbname]
        collection = db.get_collection("campaigns")
        doc = collection.find_one({"_id": ObjectId(campaign_id)})
        if not doc:
            abort(404, description="campaign not found")
        doc["_id"] = str(doc["_id"])
        return jsonify(doc)
    except Exception as e:
        current_app.logger.error("get_campaign error: %s", e)
        current_app.logger.error(traceback.format_exc())
        abort(500, description=str(e))

@fraud_bp.route("/<campaign_id>/action", methods=["POST"])
def action_campaign(campaign_id):
    """
    Body: { action: "clear" | "suspend" | "mark_reviewed", comment: "text" }
    """
    try:
        body = request.get_json(force=True)
        action = body.get("action")
        comment = body.get("comment", "")
        admin_user = body.get("admin_user", "system")

        mongo = get_mongo()
        dbname = current_app.config.get("MONGO_DB", os.environ.get("MONGO_DB", "crwdfund"))
        db = mongo[dbname]
        collection = db.get_collection("campaigns")

        update = {}
        audit = {
            "admin": admin_user,
            "action": action,
            "comment": comment,
            "at": __import__("datetime").datetime.utcnow()
        }
        if action == "clear":
            update = {"$set": {"fraud.status": "cleared"}, "$push": {"fraud.audit": audit}}
        elif action == "suspend":
            update = {"$set": {"fraud.status": "suspended"}, "$push": {"fraud.audit": audit}}
        elif action == "mark_reviewed":
            update = {"$set": {"fraud.status": "reviewed"}, "$push": {"fraud.audit": audit}}
        else:
            abort(400, description="unknown action")

        res = collection.update_one({"_id": ObjectId(campaign_id)}, update)
        if res.matched_count == 0:
            abort(404, description="campaign not found")
        return jsonify({"ok": True, "modified_count": res.modified_count})
    except Exception as e:
        current_app.logger.error("action_campaign error: %s", e)
        current_app.logger.error(traceback.format_exc())
        abort(500, description=str(e))

@fraud_bp.route("/score_campaign", methods=["POST"])
def score_campaign():
    """
    Real-time scoring endpoint.
    Body: { campaign: {...}, user: {...}, persist: true|false }
    If persist true, writes back to campaigns collection under fraud.* fields.
    """
    try:
        body = request.get_json(force=True)
        campaign = body.get("campaign") or {}
        user = body.get("user") or {}
        persist = bool(body.get("persist", True))

        detector = get_detector()
        result = detector.score_campaign(campaign, user)

        # persist to DB if campaign has _id and persist True
        if persist and campaign.get("_id"):
            mongo = get_mongo()
            dbname = current_app.config.get("MONGO_DB", os.environ.get("MONGO_DB", "crwdfund"))
            db = mongo[dbname]
            coll = db.get_collection("campaigns")
            fraud_doc = {
                "fraud.score": result["score"],
                "fraud.rule_hits": result["rule_hits"],
                "fraud.model_score": result["model_score"],
                "fraud.model_version": result.get("model_version"),
                "fraud.last_scored_at": result.get("scored_at"),
                "fraud.features_used": result.get("features_used"),
                "fraud.status": "flagged" if result["score"] >= 0.5 else "ok"
            }
            # flatten update
            update = {"$set": fraud_doc, "$push": {"fraud.audit": {"action":"auto_scored","at": __import__("datetime").datetime.utcnow()}}}
            try:
                coll.update_one({"_id": ObjectId(campaign["_id"])}, update)
            except Exception:
                current_app.logger.exception("failed to persist fraud result")

        return jsonify(result)
    except Exception as e:
        current_app.logger.error("score_campaign error: %s", e)
        current_app.logger.error(traceback.format_exc())
        abort(500, description=str(e))
