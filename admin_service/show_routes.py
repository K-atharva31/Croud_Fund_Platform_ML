# show_routes.py
from app import create_app

app = create_app()

print("✅ Loaded routes:\n")
for rule in app.url_map.iter_rules():
    print(rule)