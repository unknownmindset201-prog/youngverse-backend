import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from .config import Config
from .database import db
from . import models

from .auth import auth_bp
from .routes import notes_bp, tests_bp, batches_bp


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
from dotenv import load_dotenv
load_dotenv()

from .ai_tutor import ai_tutor_bp


def create_app():

    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, "static"),
        static_url_path="/static"
    )

    app.config.from_object(Config)

    CORS(app, supports_credentials=True)

    db.init_app(app)

    # Register APIs
    app.register_blueprint(auth_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(tests_bp)
    app.register_blueprint(batches_bp)
    app.register_blueprint(ai_tutor_bp)

    with app.app_context():
        db.create_all()

    # Health Check
    @app.route("/api/health")
    def health_check():
        return jsonify({
            "success": True,
            "message": "YoungVerse AI API is running"
        })

    # Private Admin Login
    @app.route("/admin-portal")
    def admin_portal():
        return send_from_directory(BASE_DIR, "login.html")

    # Homepage
    @app.route("/")
    def home():
        return send_from_directory(BASE_DIR, "index.html")

    # Admin Pages
    @app.route("/admin/<path:filename>")
    def admin_pages(filename):
        return send_from_directory(
            os.path.join(BASE_DIR, "admin"),
            filename
        )

    # Student Pages
    @app.route("/students/<path:filename>")
    def student_pages(filename):
        return send_from_directory(
            os.path.join(BASE_DIR, "students"),
            filename
        )

    # Parent Pages
    @app.route("/parent/<path:filename>")
    def parent_pages(filename):
        return send_from_directory(
            os.path.join(BASE_DIR, "parent"),
            filename
        )

        # Other Public Pages
    @app.route("/<path:filename>")
    def public_pages(filename):

        if filename == "login.html":
            return send_from_directory(
                BASE_DIR,
                "student-login.html"
            )

        return send_from_directory(BASE_DIR, filename)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )