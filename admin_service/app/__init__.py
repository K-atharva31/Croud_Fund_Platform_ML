from flask import Flask
from flask_pymongo import PyMongo
from flask_cors import CORS
from app.utils.jwt_auth import init_jwt
import os
from dotenv import load_dotenv

mongo = PyMongo()

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["MONGO_URI"] = os.getenv("MONGO_URI")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    CORS(app)
    mongo.init_app(app)
    init_jwt(app)

    from app.routes.admin_routes import admin_bp
    from app.routes.etl_routes import etl_bp
    from app.routes.fraud_routes import fraud_bp
    from app.routes.dashboard_routes import dashboard_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(etl_bp)
    app.register_blueprint(fraud_bp)
    app.register_blueprint(dashboard_bp)

    # @app.route("/")
    # def root():
    #     return {"message": "Admin service running", "db": app.config["MONGO_URI"]}

    return app
