from flask_jwt_extended import JWTManager

jwt = JWTManager()

def init_jwt(app):
    app.config["JWT_SECRET_KEY"] = app.config["SECRET_KEY"]
    jwt.init_app(app)
  