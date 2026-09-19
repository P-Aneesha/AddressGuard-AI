import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """
    Central configuration object. Every value is read from the
    environment - nothing sensitive is ever hardcoded here.
    """
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-not-for-production")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///addressguard_dev.db"  # local fallback so the app still runs without Neon configured
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5000")

    REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_reports")
