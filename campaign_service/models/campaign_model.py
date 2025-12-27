from flask_pymongo import ObjectId

def serialize_campaign(campaign):
    """
    Helper function to convert MongoDB document to JSON-serializable dict
    """
    return {
        "_id": str(campaign["_id"]),
        "title": campaign.get("title", ""),
        "description": campaign.get("description", ""),
        "goal_amount": campaign.get("goal_amount", 0),
        "collected_amount": campaign.get("collected_amount", 0),
        "category": campaign.get("category", ""),
        "image_url": campaign.get("image_url", ""),
        "creator_id": str(campaign.get("creator_id", "")),
        "status": campaign.get("status", "active")
    }

class CampaignModel:
    def __init__(self, mongo):
        self.collection = mongo.db.campaigns

    def create_campaign(self, data):
        """
        Create a new campaign
        """
        new_campaign = {
            "title": data["title"],
            "description": data["description"],
            "goal_amount": data["goal_amount"],
            "collected_amount": 0,
            "category": data.get("category", "General"),
            "image_url": data.get("image_url", ""),
            "creator_id": data["creator_id"],
            "status": "active"
        }
        inserted_id = self.collection.insert_one(new_campaign).inserted_id
        return str(inserted_id)

    def get_all_campaigns(self):
        """
        Retrieve all campaigns
        """
        campaigns = self.collection.find()
        return [serialize_campaign(c) for c in campaigns]

    def get_campaign_by_id(self, campaign_id):
        """
        Retrieve a single campaign by ID
        """
        campaign = self.collection.find_one({"_id": ObjectId(campaign_id)})
        if campaign:
            return serialize_campaign(campaign)
        return None

    def update_campaign(self, campaign_id, data):
        """
        Update campaign details
        """
        update_fields = {key: value for key, value in data.items() if key in [
            "title", "description", "goal_amount", "category", "image_url", "status"
        ]}
        result = self.collection.update_one(
            {"_id": ObjectId(campaign_id)}, {"$set": update_fields})
        return result.modified_count > 0

    def delete_campaign(self, campaign_id):
        """
        Delete a campaign by ID
        """
        result = self.collection.delete_one({"_id": ObjectId(campaign_id)})
        return result.deleted_count > 0

    def donate_to_campaign(self, campaign_id, amount):
        """
        Increment collected_amount when a donation is made
        """
        result = self.collection.update_one(
            {"_id": ObjectId(campaign_id)},
            {"$inc": {"collected_amount": amount}}
        )
        return result.modified_count > 0
