from pymongo import MongoClient
from app.ml.fraud_model import FraudDetector

client = MongoClient("mongodb://mongo:27017")
db = client.crwdfund
coll = db.campaigns

# ------- YOUR CUSTOM TEST CAMPAIGN ----------
campaign = {
    "_id": "TEST_CAMPAIGN_001",
    "title": "Autonomous Drone for Warehouse Scanning",
    "description": "AI drone prototype for autonomous indoor mapping. urgent funding required.",
    "creator_id": "USER_TEST_01",
    "creator_email": "prototype@mailinator.com",
    "goal": 75000,
    "amount_raised": 500,
    "created_at": "2025-10-01T00:00:00Z",
    "updates_count": 0,
    "donations_count": 12,
    "refunds_count": 4,
    "images": [],
    "video_url": None,
    "payout_country": "US",
    "country": "IN",

    # fallback user metadata
    "user_meta": {
        "created_at": "2025-09-28T00:00:00Z",
        "total_campaigns": 0,
        "payment_sources_count": 1,
        "country": "IN"
    }
}
# ---------------------------------------------

# Insert / overwrite campaign
coll.replace_one({"_id": campaign["_id"]}, campaign, upsert=True)

# Score it
det = FraudDetector()
user = campaign.get("user_meta", {})
result = det.score_campaign(campaign, user, model_weight=0.6)

# Persist fraud
coll.update_one({"_id": campaign["_id"]}, {"$set": {"fraud": result}})

print("Inserted + Scored Test Campaign")
print("Fraud Score:", result.get("score"))
print("Rule Hits:", result.get("rule_hits"))
