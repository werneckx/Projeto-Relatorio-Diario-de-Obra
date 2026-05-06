import os
from pathlib import Path
import sys
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[0]
load_dotenv(ROOT_DIR / ".env")

print(f"OS DB_PORT: {os.environ.get('DB_PORT')}")

from config import Config
print(f"Config DB_PORT: {Config.DB_PORT}")
print(f"Config SQLALCHEMY_DATABASE_URI: {Config.SQLALCHEMY_DATABASE_URI}")

from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        db.session.execute(text("SELECT 1"))
        print("Database connection successful!")
    except Exception as e:
        print(f"Database connection failed: {e}")
