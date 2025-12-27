import pandas as pd
from pymongo import MongoClient
import os
from datetime import datetime

CSV_PATH = "app/ml/fraud_training_data.csv"
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017")
DB_NAME = os.environ.get("MONGO_DB", "crwdfund")

print("Loading CSV:", CSV_PATH)
df = pd.read_csv(CSV_PATH)
print("Rows:", len(df))

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
coll = db.campaigns

docs = []
for i, r in df.iterrows():
    # safe helpers
    def get(k, default=None):
        return r[k] if k in r and pd.notna(r[k]) else default

    # prefer an explicit campaign_id column if available
    _id = get("campaign_id", None) or get("id", None) or f"csv_{i}"

    campaign = {
        "_id": _id,
        "creator_id": get("creator_id") or get("user_id") or f"user_{i}",
        "title": get("title",""),
        "description": get("description",""),
        "goal": float(get("goal",0) or 0),
        "amount_raised": float(get("amount_raised",0) or 0),
        "created_at": get("created_at"),
        "updates_count": int(get("updates_count",0) or 0),
        "donations_count": int(get("donations_count",0) or 0),
        "refunds_count": int(get("refunds_count",0) or 0),
        "images": [] if pd.isna(get("images_count",0)) or int(get("images_count",0) or 0) == 0 else list(range(int(get("images_count",0)))),
        "video_url": None if int(get("videos_count",0) or 0) == 0 else "y",
        "payout_country": get("payout_country"),
        "creator_email": get("creator_email") or (str(get("email_domain","")) if get("email_domain") else None),
        # if CSV contains user-level precomputed fields, put them on a nested user doc
        "user_meta": {
            "created_at": get("user_created_at") or None,
            "total_campaigns": int(get("user_total_campaigns",0) or 0),
            "payment_sources_count": int(get("payment_sources_count",0) or 0),
            "country": get("country")
        },
        # empty fraud placeholder
        "fraud": {}
    }
    docs.append(campaign)

# bulk insert, ignore duplicates by replacing existing docs with same _id
inserted = 0
for d in docs:
    try:
        coll.replace_one({"_id": d["_id"]}, d, upsert=True)
        inserted += 1
    except Exception as e:
        print("failed insert:", d.get("_id"), e)

print("Upserted campaigns:", inserted)
