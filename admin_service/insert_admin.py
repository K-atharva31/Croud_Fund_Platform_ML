from app import create_app, mongo
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    admin_email = "devlunagariya@gmail.com"
    existing_admin = mongo.db.users.find_one({"email": admin_email})

    if existing_admin:
        print("✅ Admin already exists:", existing_admin["email"])
    else:
        mongo.db.users.insert_one({
            "name": "Dev Lunagariya",
            "email": admin_email,
            "password": generate_password_hash("admin123"),
            "role": "admin",
            "status": "active"
        })
        print("🎉 Admin created successfully ->", admin_email)
