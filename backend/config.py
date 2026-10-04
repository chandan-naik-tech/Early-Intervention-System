"""Connection settings: everything is read from backend/.env"""
import os
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda *a, **k: None
BASE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE, ".env"))
DB_PATH = os.path.join(BASE, os.getenv("DB_FILE", "portal.db"))   # always the same file, whatever folder you run from
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
