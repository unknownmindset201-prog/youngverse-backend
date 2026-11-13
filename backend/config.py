import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

APP_ENV = os.environ.get(
    "APP_ENV",
    "production" if os.environ.get("RENDER") else "development"
).lower()

IS_PRODUCTION = APP_ENV == "production"

SECRET_KEY = os.environ.get("SECRET_KEY")

if IS_PRODUCTION and not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be configured in production")

if not SECRET_KEY:
    SECRET_KEY = "youngverse-local-development-only"


class Config:
    APP_ENV = APP_ENV
    SECRET_KEY = SECRET_KEY

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://", "postgresql://", 1
        )

    SQLALCHEMY_DATABASE_URI = (
        DATABASE_URL or f"sqlite:///{BASE_DIR / 'youngverse.db'}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024

    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    SESSION_COOKIE_SAMESITE = "None" if IS_PRODUCTION else "Lax"
    SESSION_REFRESH_EACH_REQUEST = True
