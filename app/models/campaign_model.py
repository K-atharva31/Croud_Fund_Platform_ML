from app import mongo
from bson import ObjectId
from datetime import datetime

class CampaignModel:
    def __init__(self, title, description, funding_goal, deadline, category, creator_id, image_url, rewards, funded_amount=0, status='active'):
        self.title = title
        self.description = description
        self.funding_goal = funding_goal
        self.funded_amount = funded_amount  # Default value set here
        self.deadline = deadline
        self.category = category
        self.status = status  # 'active' by default, can be 'completed' if funding goal is reached
        self.creator_id = creator_id
        self.image_url = image_url
        self.rewards = rewards
        self.created_at = datetime.utcnow()

    def save_to_db(self):
        campaign_data = {
            "title": self.title,
            "description": self.description,
            "funding_goal": self.funding_goal,
            "funded_amount": self.funded_amount,
            "deadline": self.deadline,
            "category": self.category,
            "status": self.status,
            "creator_id": self.creator_id,
            "image_url": self.image_url,
            "rewards": self.rewards,
            "created_at": self.created_at
        }
        result = mongo.db.campaigns.insert_one(campaign_data)
        return result.inserted_id

    @classmethod
    def find_by_id(cls, campaign_id):
        campaign = mongo.db.campaigns.find_one({"_id": ObjectId(campaign_id)})
        if campaign:
            return cls(
                title=campaign["title"],
                description=campaign["description"],
                funding_goal=campaign["funding_goal"],
                funded_amount=campaign["funded_amount"],
                deadline=campaign["deadline"],
                category=campaign["category"],
                status=campaign["status"],
                creator_id=campaign["creator_id"],
                image_url=campaign["image_url"],
                rewards=campaign["rewards"]
            )
        return None

    @classmethod
    def update_campaign(cls, campaign_id, data):
        result = mongo.db.campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {"$set": data}
        )
        return result.modified_count > 0

    @classmethod
    def check_and_update_funding_status(cls, campaign_id):
        campaign = cls.find_by_id(campaign_id)
        if campaign and campaign.funded_amount >= campaign.funding_goal:
            campaign.status = 'completed'
            cls.update_campaign(campaign_id, {"status": "completed"})
            return True
        return False
