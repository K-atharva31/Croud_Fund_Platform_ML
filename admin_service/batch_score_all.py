from pymongo import MongoClient
from app.ml.fraud_model import FraudDetector
import os

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017")
DB = os.environ.get("MONGO_DB", "crwdfund")
client = MongoClient(MONGO_URI)
db = client[DB]
coll = db.campaigns

detector = FraudDetector()

count = 0
for c in coll.find({}):
    try:
        # try to materialize a user doc if present in users collection
        user = {}
        if 'creator_id' in c:
            u = db.users.find_one({'_id': c['creator_id']})
            if u:
                user = u
            else:
                # fallback to user_meta if we stored it during import
                user = c.get('user_meta', {})
        result = detector.score_campaign(c, user, model_weight=0.6)
        # Persist a compact fraud doc
        fraud_doc = {
            "score": result["score"],
            "model_score": result["model_score"],
            "model_version": result["model_version"],
            "rule_hits": result["rule_hits"],
            "scored_at": result["scored_at"]
        }
        coll.update_one({"_id": c["_id"]}, {"$set": {"fraud": fraud_doc}})
        count += 1
        if count % 200 == 0:
            print("Scored", count)
    except Exception as e:
        print("Error scoring", c.get("_id"), e)
print("Batch scoring complete. Scored:", count)
