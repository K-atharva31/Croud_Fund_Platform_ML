from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os
from extensions import mongo  # ✅ import from extensions

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MONGO_URI"] = "mongodb://mongo:27017/campaign_db"
app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "uploads")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

CORS(app)
mongo.init_app(app)

# ✅ Import and register blueprints
from routes.campaign_routes import campaign_bp
app.register_blueprint(campaign_bp, url_prefix="/api")

from routes.investor_routes import investor_bp
app.register_blueprint(investor_bp, url_prefix="/investor")


# ✅ Serve the homepage (root)
@app.route("/")
def serve_home():
    return send_from_directory(app.static_folder, "index.html")


# ✅ Serve all other static files safely
@app.route("/<path:filename>")
def serve_static_files(filename):
    file_path = os.path.join(app.static_folder, filename)
    if os.path.exists(file_path):
        return send_from_directory(app.static_folder, filename)
    return jsonify({"error": "File not found"}), 404


@app.route("/test")
def test():
    try:
        mongo.db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "not connected"
    return jsonify({"service": "campaign_service", "db_status": db_status})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
