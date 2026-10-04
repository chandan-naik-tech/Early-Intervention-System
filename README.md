# AI-Driven Early Intervention System for Educational Institutions
    early_intervention/
      backend/   Flask app, database logic, ML + AI code, .env (connection file)
      frontend/  templates (HTML) and static (CSS)

## Quick start
Windows: double-click `start.bat`. Mac/Linux: run `./start.sh`. Or run `python start_app.py` from this folder.
It installs the packages and creates the database on the first run, opens your browser, and starts the site.

## Manual run
    cd backend
    pip install -r requirements.txt
    python init_db.py
    python app.py          # http://127.0.0.1:5000

Edit `backend/.env` to change the database file, secret key, Gemini key and Twilio keys.
Logins: admin@demo.com/admin123 · parent1@demo.com/aarav@101 · nair@demo.com/nair@fac1 (Sem 1 advisor) · pillai@demo.com/pillai@fac9 (faculty, Sem 1 and 5).
All emails and passwords are listed on the admin "Users & logins" page.
