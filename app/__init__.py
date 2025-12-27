from flask import Flask
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash
from flask import send_from_directory
import os
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from flask_cors import CORS


mongo = PyMongo()

def create_app():
    app = Flask(__name__, static_folder='../build', static_url_path='/')
    CORS(app, supports_credentials=True, origins=["http://localhost:5000", "http://127.0.0.1:5000"])

    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static/uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        return send_from_directory(UPLOAD_FOLDER, filename)

    # Secret key for session management
    app.config['SECRET_KEY'] = 'this_is_a_very_secret_key_12345'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = False  # Change to True when deploying on HTTPS


    # Local MongoDB connection (main working database)
    app.config["MONGO_URI"] = "mongodb://localhost:27017/crowdfundingDB"

    client = MongoClient("mongodb://localhost:27017/crowdfundingDB")
    db = client['crowdfunding_db']

    users_col = db['users']
    campaigns_col = db['campaigns']
    investments_col = db['investments']

    # Export collections so other modules can import
    __all__ = ['users_col', 'campaigns_col', 'investments_col']

    # Cloud MongoDB connection string (used only for ETL Migration)
    app.config["MONGO_ATLAS_URI"] = "mongodb+srv://etluser:test1234@cluster0.qresf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" 
    #Initialize Flask-PyMongo (for local use only)
    mongo.init_app(app)

    # Serve React frontend
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')


    # === Auto-Create Main Admin (on First Run) ===
    with app.app_context():
        from flask import current_app
        current_app.users_col = users_col
        current_app.campaigns_col = campaigns_col
        current_app.investments_col = investments_col

        ensure_main_admin()

    # Import and register all blueprints
    from app.routes.admin_routes import admin_bp
    from app.routes.creator_routes import creator_bp
    from app.routes.investor_routes import investor_bp
    from app.routes.etl_pipeline import etl_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(creator_bp, url_prefix="/creator")
    app.register_blueprint(investor_bp, url_prefix="/investor")
    app.register_blueprint(etl_bp, url_prefix="/etl")

    return app


def ensure_main_admin():
    main_admin_email = "21bce036@nirmauni.ac.in"
    existing_admin = mongo.db.users.find_one({"email": main_admin_email})

    if not existing_admin:
        main_admin = {
            "name": "Rudra Chaudhari",
            "email": main_admin_email,
            "password": generate_password_hash("MajorProject_8"),  # Hashing the password
            "role": "admin"
        }
        mongo.db.users.insert_one(main_admin)
        print("✅ Main Admin (Rudra Chaudhari) auto-created in DB.")
    else:
        print("✅ Main Admin already exists. Skipping auto-creation.")



