import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_wtf.csrf import generate_csrf

from .config import Config
from .database import db
from . import models
from .extensions import limiter

from .auth import auth_bp
from .routes import notes_bp, tests_bp, batches_bp
from .ai_tutor import ai_tutor_bp
from .notifications import notifications_bp


def create_app():

    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "static"),
        static_url_path="/static"
    )

    app.config.from_object(Config)

    allowed_origins = [
        "https://youngverseai.netlify.app",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5000",
        "http://127.0.0.1:5000"
    ]

    CORS(
        app,
        origins=allowed_origins,
        supports_credentials=True
    )

    limiter.init_app(app)
    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(tests_bp)
    app.register_blueprint(batches_bp)
    app.register_blueprint(ai_tutor_bp)
    app.register_blueprint(notifications_bp)

    with app.app_context():
        db.create_all()

    @app.route("/api/health", methods=["GET"])
    def health_check():

        registered_routes = {
            rule.rule for rule in app.url_map.iter_rules()
        }

        return jsonify({
            "success": True,
            "message": "YoungVerse AI Backend Running",
            "environment": app.config.get("APP_ENV", "configured"),
            "csrf_route_registered": (
                "/api/csrf-token" in registered_routes
            )
        }), 200

    @app.route("/api/csrf-token", methods=["GET"])
    def get_csrf_token():

        return jsonify({
            "success": True,
            "csrf_token": generate_csrf()
        }), 200

    @app.route("/admin-portal")
    def admin_portal():
        return send_from_directory(BASE_DIR, "login.html")

    @app.route("/")
    def home():
        return send_from_directory(BASE_DIR, "index.html")

    @app.route("/admin/<path:filename>")
    def admin_pages(filename):
        return send_from_directory(BASE_DIR / "admin", filename)

    @app.route("/students/<path:filename>")
    def student_pages(filename):
        return send_from_directory(BASE_DIR / "students", filename)

    @app.route("/parent/<path:filename>")
    def parent_pages(filename):
        return send_from_directory(BASE_DIR / "parent", filename)

    @app.route("/<path:filename>")
    def public_pages(filename):

        if filename == "login.html":
            return send_from_directory(BASE_DIR, "student-login.html")

        return send_from_directory(BASE_DIR, filename)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
