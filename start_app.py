"""One-click launcher: installs packages (first run), builds the database (first run), opens the browser and starts the server."""
import os, subprocess, sys, threading, webbrowser
ROOT = os.path.dirname(os.path.abspath(__file__)); BACK = os.path.join(ROOT, "backend")
try:
    import flask, xgboost, numpy, requests, twilio, dotenv
except ImportError:
    print("Installing required packages (first run only, needs internet)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", os.path.join(BACK, "requirements.txt")])
os.chdir(BACK)
if not os.path.exists("portal.db"):
    print("Creating the database with demo data...")
    subprocess.check_call([sys.executable, "init_db.py"])
print("Starting the website at http://127.0.0.1:5000  (press Ctrl+C to stop)")
threading.Timer(3, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
subprocess.call([sys.executable, "app.py"])
