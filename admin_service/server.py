from app import create_app
from flask import send_from_directory
import os

# Initialize Flask app from your factory
app = create_app()

# Absolute path to the admin_service directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/admin")
def serve_admin_dashboard():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(base_dir, "admin_frontend.html", mimetype="text/html")

@app.route("/")
def root_redirect():
    return serve_admin_dashboard()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5005))
    print(f"🚀 Starting Admin Service on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
