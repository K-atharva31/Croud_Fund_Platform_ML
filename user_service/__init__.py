from flask import Flask, send_from_directory
from flask_pymongo import PyMongo
from flask_cors import CORS
import os

mongo = PyMongo()

def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config["MONGO_URI"] = "mongodb://mongo:27017/users_db"
    CORS(app)
    mongo.init_app(app)

    # Import and register blueprints
    from routes.user_routes import user_bp
    app.register_blueprint(user_bp)

    # Serve the test HTML page
    @app.route('/')
    def home():
        index_path = os.path.join(app.root_path, 'static', 'index.html')
        return send_from_directory(os.path.dirname(index_path), 'index.html')

    return app

