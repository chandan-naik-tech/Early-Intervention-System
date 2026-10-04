import os, sqlite3
from functools import wraps
from flask import Flask, g, render_template, request, redirect, session, flash
from werkzeug.security import check_password_hash
import config, ml, ai_summary, alerts
app = Flask(__name__, template_folder="../frontend/templates", static_folder="../frontend/static")
app.secret_key = config.SECRET_KEY
THRESH = 75
TITLE = "AI-Driven Early Intervention System for Educational Institutions"

def db():
    if "db" not in g:
        g.db = sqlite3.connect(config.DB_PATH); g.db.row_factory = sqlite3.Row
    return g.db
@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()
def q(sql, a=(), one=False):
    r = db().execute(sql, a).fetchall()
    return (r[0] if r else None) if one else r
def run(sql, a=()):
    db().execute(sql, a); db().commit()

def analyse(s):
    i = (s["id"],)
    att = q("select avg(present)*100 v from attendance where student_id=?", i, True)["v"] or 0
    avg = q("select avg(score) v from marks where student_id=?", i, True)["v"] or 0
    late = q("select avg(days_late) v from submissions where student_id=?", i, True)["v"] or 0
    a = dict(att=round(att, 1), avg=round(avg, 1), late=round(late, 1))
    a["pred"] = ml.predict(a["att"], a["avg"], a["late"])
    why = []
    if a["att"] < THRESH: why.append(f"Attendance below {THRESH}%")
    if a["pred"] < 40: why.append("Predicted final score below 40")
    a["risk"], a["why"] = bool(why), why
    return a

def need(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            return f(*a, **k) if session.get("role") in roles else redirect("/")
        return w
    return deco

def allowed_sems():
    if session.get("role") == "admin": return list(range(1, 9))
    u = q("select sems from users where id=?", (session["uid"],), True)
    return sorted({int(x) for x in (u["sems"] or "").split(",") if x.strip().isdigit()})
def cur_sem():
    if session["role"] == "parent":
        return q("select s.sem v from users u join students s on s.id=u.student_id where u.id=?", (session["uid"],), True)["v"]
    al = allowed_sems(); s = request.args.get("sem", type=int) or session.get("sem")
    if s not in al: s = al[0] if al else 1
    session["sem"] = s; return s
def can_adv(sem):
    if session.get("role") == "admin": return True
    u = q("select adv_sem v from users where id=?", (session["uid"],), True) if session.get("role") == "faculty" else None
    return bool(u and u["v"] == sem)
def adv_ok(): return can_adv(cur_sem())
def advisor(f):
    @wraps(f)
    def w(*a, **k):
        if adv_ok(): return f(*a, **k)
        flash("Only this semester's class advisor or admin can do that."); return redirect("/staff")
    return w
@app.context_processor
def inject():
    if not session.get("uid"): return dict(TITLE=TITLE)
    return dict(TITLE=TITLE, adv=adv_ok(), admin=session["role"] == "admin", sem=cur_sem(), sems=[] if session["role"] == "parent" else allowed_sems())

@app.route("/", methods=["GET", "POST"])
def login():
    want = request.form.get("role", "")
    if request.method == "POST":
        u = q("select * from users where email=?", (request.form["email"].strip().lower(),), True)
        kind = None if not u else ("admin" if u["role"] == "admin" else "parent" if u["role"] == "parent" else "advisor" if u["is_advisor"] else "faculty")
        if u and check_password_hash(u["password"], request.form["password"]) and kind == want:
            session.clear(); session.update(uid=u["id"], role=u["role"], name=u["name"])
            return redirect("/parent" if u["role"] == "parent" else "/staff")
        flash("Login failed. Check the email and password, and make sure you chose the right role.")
    return render_template("login.html", role=want)
@app.route("/logout")
def logout(): session.clear(); return redirect("/")

FORMS = {"attendance": ("attendance", ["student_id", "date", "present"]), "marks": ("marks", ["student_id", "subject", "exam", "score"]),
         "submissions": ("submissions", ["student_id", "title", "days_late"]), "announcements": ("announcements", ["title", "body"])}
@app.route("/add/<kind>", methods=["POST"])
@need("admin", "faculty")
def add(kind):
    t, cols = FORMS[kind]; vals = [request.form[c] for c in cols]
    if kind == "announcements": cols, vals = ["sem"] + cols, [cur_sem()] + vals
    else:
        s = q("select sem from students where id=?", (request.form["student_id"],), True)
        if not s or s["sem"] not in allowed_sems(): flash("You do not have access to that semester."); return redirect("/staff")
    run(f"insert or replace into {t} ({','.join(cols)}) values ({','.join('?' * len(cols))})", vals)
    flash("Saved."); return redirect("/staff")

@app.route("/alerts", methods=["POST"])
@need("admin", "faculty")
@advisor
def send_alerts():
    ch, n = request.form["channel"], 0
    for s in q("select * from students where sem=?", (cur_sem(),)):
        a = analyse(s)
        if a["risk"]:
            ps = q("select phone from users where student_id=? and role='parent'", (s["id"],))
            msg = f"Early-intervention alert: {s['name']} is at risk. Attendance {a['att']}%, predicted final score {a['pred']}/100. Please contact the faculty."
            run("insert into alerts(student_id,channel,message,status) values(?,?,?,?)", (s["id"], ch, msg, ", ".join(alerts.send(p["phone"], msg, ch) for p in ps)[:120])); n += 1
    flash(f"{n} alert(s) sent to parents of at-risk students."); return redirect("/staff")

import extra, portal_ai, ai2
extra.register(app, db, q, run, analyse, need, advisor, adv_ok, can_adv, cur_sem)
portal_ai.register(app, q, run, analyse, need, THRESH, cur_sem)
ai2.register(app, q, analyse, need, THRESH, allowed_sems)

if __name__ == "__main__":
    if not os.path.exists(config.DB_PATH): import init_db
    app.run(debug=True)
