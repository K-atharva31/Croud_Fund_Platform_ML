# admin_service/app/ml/train_fraud_model.py
import os, joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime, timezone, timedelta

# import your feature builder
from app.ml.feature_engineering import compute_features_for_campaign

CSV_PATH = "app/ml/fraud_training_data.csv"  # adjust if elsewhere
MODEL_DIR = "app/ml/models"
MODEL_PATH = os.path.join(MODEL_DIR, "isoforest_v1.joblib")

os.makedirs(MODEL_DIR, exist_ok=True)

def row_to_campaign_user(row):
    # Build minimal campaign/user dict that compute_features_for_campaign expects
    campaign = {
        "goal": float(row.get("goal", 0)),
        "amount_raised": float(row.get("amount_raised", 0)),
        "created_at": row.get("created_at"),
        "updates_count": int(row.get("updates_count", 0)),
        "donations_count": int(row.get("donations_count", 0)),
        "refunds_count": int(row.get("refunds_count", 0)),
        "images": [] if pd.isna(row.get("images_count")) else list(range(int(row.get("images_count", 0)))),
        "video_url": None if int(row.get("videos_count", 0))==0 else "y",
        "payout_country": row.get("payout_country")
    }
    try:
        days = float(row.get("user_account_age_days", 9999))
        created_at = (datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(days=days)).isoformat() + "Z"
    except Exception:
        created_at = None
    user = {
        "created_at": created_at,
        "total_campaigns": int(row.get("user_total_campaigns", 0)),
        "payment_sources_count": int(row.get("payment_sources_count", 0)),
        "email": (row.get("email_domain") or "nobody@example.com"),
        "country": row.get("country")
    }
    return campaign, user

print("Loading CSV:", CSV_PATH)
df = pd.read_csv(CSV_PATH)
print("Rows:", len(df))

feature_rows = []
for _, row in df.iterrows():
    campaign, user = row_to_campaign_user(row)
    feats = compute_features_for_campaign(campaign, user)
    feature_rows.append(feats)

X = pd.DataFrame(feature_rows).fillna(0.0).astype(float)
print("Feature matrix:", X.shape)

# Train IsolationForest
model = IsolationForest(n_estimators=200, contamination="auto", random_state=42)
model.fit(X.values)

version = f"isof_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
setattr(model, "model_version", version)

joblib.dump(model, MODEL_PATH)
joblib.dump(model, "/app/ml/models/isoforest_v1.joblib")

print("Saved model:", MODEL_PATH)
print("Model version:", version)
