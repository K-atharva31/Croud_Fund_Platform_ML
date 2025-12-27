# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/crowdfunding")
    MAIN_ADMIN_EMAIL = os.getenv("MAIN_ADMIN_EMAIL", "devlunagariya@gmail.com")
