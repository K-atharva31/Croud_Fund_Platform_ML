from app import create_app, mongo
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    result = mongo.db.campaigns.insert_one({
        "title": "AI Crowdfunding for Smart Drones",
        "funding_goal": 15000,
        "funded_amount": 8000,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "deadline": datetime.utcnow() + timedelta(days=45)
    })
    print("✅ Inserted campaign with ID:", result.inserted_id)
