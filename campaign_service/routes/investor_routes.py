# routes/investor_routes.py
from flask import Blueprint, request, jsonify, current_app, session
from datetime import datetime
import os
from bson import ObjectId
import razorpay
from werkzeug.exceptions import BadRequest

# blueprint
investor_bp = Blueprint("investor_bp", __name__)

# read keys from env (set in docker-compose or container env)
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# init razorpay client (will work even if keys are empty; calls will fail gracefully)
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def get_mongo():
    """Helper: return pymongo instance from flask app extensions (same pattern as your app)."""
    return current_app.extensions.get("pymongo").cx if False else current_app.extensions["pymongo"]


def get_db():
    """Return db handle (works with flask_pymongo): current_app.extensions['pymongo'].db or .cx[db_name]."""
    pymongo_ext = current_app.extensions.get("pymongo")
    # flask_pymongo sets extension object with .db attribute after init_app
    if hasattr(pymongo_ext, "db"):
        return pymongo_ext.db
    # fallback to client/cx
    if hasattr(pymongo_ext, "cx"):
        dbname = current_app.config.get("MONGO_DBNAME") or current_app.config.get("MONGO_URI", "").rsplit("/", 1)[-1]
        return pymongo_ext.cx[dbname]
    raise RuntimeError("Cannot access mongo db from app extensions")


# ---------------------------
# Endpoint: create order
# ---------------------------
@investor_bp.route("/create-razorpay-order", methods=["POST"])
def create_razorpay_order():
    """
    Expects JSON: { amount: number }  where amount is in INR (e.g. 500.00)
    Returns: { order_id, amount, currency, razorpay_key }
    """
    try:
        payload = request.get_json(force=True)
    except BadRequest:
        return jsonify({"message": "Invalid JSON"}), 400

    amount = payload.get("amount")
    try:
        amount = float(amount)
    except Exception:
        return jsonify({"message": "Invalid amount"}), 400

    if amount <= 0:
        return jsonify({"message": "Amount must be > 0"}), 400

    # razorpay expects amount in paise
    amount_paise = int(round(amount * 100))

    try:
        order = razorpay_client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "payment_capture": 1  # auto capture; change if you want manual capture
        })
    except Exception as e:
        current_app.logger.exception("Razorpay order creation failed")
        return jsonify({"message": "Payment gateway error"}), 500

    return jsonify({
        "order_id": order.get("id"),
        "amount": order.get("amount"),
        "currency": order.get("currency"),
        "razorpay_key": RAZORPAY_KEY_ID
    }), 200


# ---------------------------
# Helper: simple fraud scoring placeholder
# ---------------------------
def score_investment_simple(invest_doc):
    """
    Lightweight rule-based scoring. Returns (score: float 0..1, label: 'ok'|'review'|'fraud', reasons:list)
    Replace or extend with ML model call later.
    """
    reasons = []
    score = 0.0
    try:
        amt = float(invest_doc.get("amount", 0))
    except Exception:
        amt = 0.0

    # rule: very large single payment -> suspicious
    if amt >= 100000:
        score += 0.6
        reasons.append("large_amount")

    # rule: new account (if investor_id present and account_age < 3 days)
    inv_id = invest_doc.get("investor_id")
    if inv_id:
        try:
            db = get_db()
            user = db.users.find_one({"_id": ObjectId(inv_id)})
            if user and user.get("created_at"):
                delta = datetime.utcnow() - user["created_at"]
                if delta.days < 3:
                    score += 0.25
                    reasons.append("new_account")
        except Exception:
            # don't fail scoring on DB errors
            pass

    # clamp
    score = min(1.0, score)

    if score >= 0.7:
        label = "fraud"
    elif score >= 0.35:
        label = "review"
    else:
        label = "ok"

    return score, label, reasons


# ---------------------------
# Endpoint: record investment (called by frontend after Razorpay handler)
# ---------------------------
@investor_bp.route("/invest", methods=["POST"])
def record_investment():
    """
    Expected JSON from frontend (after Razorpay checkout success handler):
    {
      campaign_id: "<mongo id>",
      investment_amount: 1234.50,
      payment_id: "razorpay_payment_id",
      order_id: "razorpay_order_id",
      signature: "razorpay_signature"
    }
    """
    try:
        payload = request.get_json(force=True)
    except BadRequest:
        return jsonify({"message": "Invalid JSON"}), 400

    campaign_id = payload.get("campaign_id")
    amount = payload.get("investment_amount")
    payment_id = payload.get("payment_id")
    order_id = payload.get("order_id")
    signature = payload.get("signature")

    if not (campaign_id and amount and payment_id and order_id and signature):
        return jsonify({"message": "Missing required fields"}), 400

    # Verify Razorpay payment signature to ensure integrity
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })
        signature_ok = True
    except Exception:
        current_app.logger.warning("Razorpay signature verification failed for order %s", order_id)
        signature_ok = False

    # build investment doc
    db = get_db()
    invest_doc = {
        "campaign_id": ObjectId(campaign_id) if ObjectId.is_valid(campaign_id) else campaign_id,
        "investor_id": session.get("user_id") or None,
        "amount": float(amount),
        "currency": "INR",
        "payment_id": payment_id,
        "order_id": order_id,
        "signature": signature,
        "status": "paid" if signature_ok else "pending",
        "fraud_score": None,
        "fraud_label": None,
        "meta": {
            "ip": request.remote_addr,
            "user_agent": request.headers.get("User-Agent"),
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    res = db.investments.insert_one(invest_doc)
    invest_id = res.inserted_id

    # If signature OK → run fraud scoring (synchronous lightweight). For heavy ML call, do async job.
    try:
        if signature_ok:
            score, label, reasons = score_investment_simple(invest_doc)
            db.investments.update_one({"_id": invest_id}, {"$set": {
                "fraud_score": score,
                "fraud_label": label,
                "updated_at": datetime.utcnow()
            }})
            # if ok then update campaign funded amount, else create alert
            if label == "ok":
                db.campaigns.update_one({"_id": ObjectId(campaign_id)}, {"$inc": {"funded_amount": float(amount)}})
            else:
                # create a fraud alert record
                db.fraud_alerts.insert_one({
                    "investment_id": invest_id,
                    "campaign_id": ObjectId(campaign_id),
                    "score": score,
                    "reasons": reasons,
                    "created_at": datetime.utcnow(),
                    "status": "open"
                })
                # mark investment flagged
                db.investments.update_one({"_id": invest_id}, {"$set": {"status": "flagged"}})
        else:
            # signature not ok -> mark as flagged/pending
            db.investments.update_one({"_id": invest_id}, {"$set": {"status": "flagged", "updated_at": datetime.utcnow()}})
    except Exception:
        current_app.logger.exception("Error post-processing investment")

    return jsonify({"message": "Investment recorded", "investment_id": str(invest_id)}), 200


# ---------------------------
# Webhook endpoint for Razorpay (optional, recommended)
# ---------------------------
@investor_bp.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    """
    Protect with the webhook secret set in RAZORPAY_WEBHOOK_SECRET env var.
    Razorpay will POST JSON; we verify signature and handle events like payment.captured.
    """
    payload = request.data
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature or not RAZORPAY_WEBHOOK_SECRET:
        current_app.logger.warning("Webhook called but missing signature or webhook secret")
        return jsonify({"message": "Missing signature or webhook secret"}), 400

    try:
        razorpay_client.utility.verify_webhook_signature(payload, signature, RAZORPAY_WEBHOOK_SECRET)
    except Exception:
        current_app.logger.exception("Invalid webhook signature")
        return jsonify({"message": "Invalid signature"}), 400

    event = request.get_json(force=True)
    # handle payment captured event
    try:
        if event.get("event") == "payment.captured":
            payment = event["payload"]["payment"]["entity"]
            order_id = payment.get("order_id")
            payment_id = payment.get("id")
            amount = payment.get("amount", 0)/100.0
            # update investment record(s) with this order_id
            db = get_db()
            db.investments.update_one({"order_id": order_id}, {"$set": {
                "payment_id": payment_id,
                "status": "paid",
                "updated_at": datetime.utcnow()
            }})
            # optionally increment campaign funded_amount if not already incremented
            # (you may want idempotency checks here)
    except Exception:
        current_app.logger.exception("Error handling webhook payload")

    return jsonify({"ok": True}), 200

@investor_bp.route("/my-investments", methods=["GET"])
def my_investments():
    """Return all investments for the current user (or all, if session not enforced yet)."""
    db = get_db()
    user_id = session.get("user_id")

    query = {}
    if user_id:
        query["investor_id"] = user_id  # adjust if you store ObjectId

    investments = list(db.investments.find(query).sort("created_at", -1))

    # fetch campaign titles (optional join)
    campaigns_map = {str(c["_id"]): c.get("title", "") for c in db.campaigns.find({}, {"title": 1})}
    for inv in investments:
        inv["_id"] = str(inv["_id"])
        inv["campaign_id"] = str(inv.get("campaign_id"))
        inv["campaign_title"] = campaigns_map.get(inv["campaign_id"], "")
        inv["created_at"] = inv.get("created_at", datetime.utcnow())

    return jsonify({"investments": investments}), 200
