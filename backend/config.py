import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:

    SECRET_KEY = os.environ.get("SECRET_KEY")

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1
        )

    SQLALCHEMY_DATABASE_URI = (
        DATABASE_URL
        or f"sqlite:///{BASE_DIR / 'youngverse.db'}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 15 * 1024 * 1024

    PERMANENT_SESSION_LIFETIME = 3600

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
