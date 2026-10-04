import csv, io, sqlite3
from flask import request, redirect, render_template, session, flash, Response
from werkzeug.security import generate_password_hash as h
ordn = lambda n: f"{n}{'st' if n == 1 else 'nd' if n == 2 else 'rd' if n == 3 else 'th'} Sem"

def register(app, db, q, run, analyse, need, advisor, adv_ok, can_adv, cur_sem):
    ALL, STAFF = ("parent", "admin", "faculty"), ("admin", "faculty")
    def sid(): return q("select student_id v from users where id=?", (session["uid"],), True)["v"]
    def like(sem): return f"%,{sem},%"
    def add_user(name, email, pw, role, phone=None, lang=None, student=None, subject=None, sems=""):
        cur = db().execute("insert into users(name,email,password,plain,role,phone,lang,student_id,subject,sems) values(?,?,?,?,?,?,?,?,?,?)",
                           (name, email.strip().lower(), h(pw), pw, role, phone, lang, student, subject, sems)); db().commit(); return cur.lastrowid
    def clean(s): return ",".join(sorted({x.strip() for x in s.split(",") if x.strip().isdigit() and 1 <= int(x) <= 8}))

    @app.route("/timetable", methods=["GET", "POST"])
    @need(*ALL)
    def timetable():
        sem = cur_sem()
        if request.method == "POST":
            if adv_ok(): run("insert into timetable values(?,?,?,?,?)", [sem] + [request.form[k] for k in ("day", "time", "subject", "faculty")]); flash("Slot added.")
            else: flash("Only this semester's class advisor or admin can change the timetable.")
        return render_template("timetable.html", rows=q("select rowid id, * from timetable where sem=? order by rowid", (sem,)),
                               fac=q("select name from users where role='faculty' and (',' || sems || ',') like ?", (like(sem),)))

    @app.route("/timetable/delete/<int:i>", methods=["POST"])
    @need(*STAFF)
    def del_slot(i):
        r = q("select sem from timetable where rowid=?", (i,), True)
        if r and can_adv(r["sem"]): run("delete from timetable where rowid=?", (i,))
        return redirect("/timetable")

    @app.route("/messages", methods=["GET", "POST"])
    @need(*ALL)
    def messages():
        P, sem = session["role"] == "parent", cur_sem()
        if request.method == "POST":
            f = request.form
            if P: v = (sid(), session["uid"], "Parent", f["body"], f["faculty_id"])
            else:
                pu = q("select student_id v from users where id=? and role='parent'", (f["parent_id"],), True)
                v = (pu["v"], f["parent_id"], session["name"], f["body"], session["uid"])
            run("insert into messages(student_id,parent_id,sender,body,faculty_id) values(?,?,?,?,?)", v); flash("Message sent."); return redirect("/messages")
        base = "select m.rowid mid, m.*, s.name, f.name fname from messages m join students s on s.id=m.student_id left join users f on f.id=m.faculty_id"
        if P: rows = q(base + " where m.parent_id=? order by m.rowid", (session["uid"],))
        elif session["role"] == "admin": rows = q(base + " order by m.rowid desc limit 40")
        else: rows = q(base + " where m.faculty_id=? order by m.rowid desc limit 40", (session["uid"],))
        return render_template("messages.html", rows=rows, parents=q("select u.id, u.name, u.email from users u join students s on s.id=u.student_id where u.role='parent' and s.sem=? order by u.name", (sem,)),
            faculty=q("select id, name, subject, is_advisor from users where role='faculty' and (',' || sems || ',') like ? order by is_advisor desc, name", (like(sem),)))

    @app.route("/leave", methods=["GET", "POST"])
    @need(*ALL)
    def leave():
        P = session["role"] == "parent"
        if request.method == "POST" and P:
            run("insert into leaves(student_id,reason,from_date,to_date) values(?,?,?,?)", (sid(), request.form["reason"], request.form["from_date"], request.form["to_date"])); flash("Leave request sent."); return redirect("/leave")
        base = "select l.*, s.name from leaves l join students s on s.id=l.student_id"
        return render_template("leave.html", rows=q(base + " where l.student_id=? order by l.id desc", (sid(),)) if P else q(base + " where s.sem=? order by l.id desc", (cur_sem(),)))

    @app.route("/leave/<int:i>/<st>", methods=["POST"])
    @need(*STAFF)
    def leave_set(i, st):
        l = q("select l.id, s.sem from leaves l join students s on s.id=l.student_id where l.id=?", (i,), True)
        if st in ("Approved", "Rejected") and l and can_adv(l["sem"]):
            run("update leaves set status=?, reviewed_by=?, reviewed_on=datetime('now') where id=?", (st, session["name"], i))
            flash(f"Leave request #{i} {st.lower()} and saved to the database.")
        else: flash("Only the class advisor of that semester or admin can review this request.")
        return redirect("/leave")

    @app.route("/attendance", methods=["GET", "POST"])
    @need(*STAFF)
    def attendance():
        sem = cur_sem(); d = request.values.get("date") or q("select date('now') v", one=True)["v"]; st = q("select * from students where sem=?", (sem,))
        if request.method == "POST":
            for s in st: run("insert or replace into attendance values(?,?,?)", (s["id"], d, int(request.form.get(f"s{s['id']}") == "1")))
            flash(f"Attendance saved for {d}. Parents can see it now."); return redirect(f"/attendance?date={d}")
        return render_template("attendance.html", d=d, rows=st, cur={r["student_id"]: r["present"] for r in q("select * from attendance where date=?", (d,))})

    @app.route("/students")
    @need(*STAFF)
    def students(): return render_template("students.html", rows=[(s, analyse(s)) for s in q("select * from students where sem=?", (cur_sem(),))])

    @app.route("/students/add", methods=["POST"])
    @need("admin")
    def add_student():
        f = request.form; sem = int(f["sem"])
        try:
            cur = db().execute("insert into students(name,roll,class,sem) values(?,?,?,?)", (f["name"], f["roll"], ordn(sem) + " B.E", sem))
            add_user(f"Parent of {f['name']}", f["email"], f["password"], "parent", f["phone"], f["lang"], cur.lastrowid); flash("Student and parent login created.")
        except sqlite3.IntegrityError: db().rollback(); flash("That email is already in use.")
        return redirect(f"/students?sem={sem}")

    @app.route("/students/delete/<int:i>", methods=["POST"])
    @need("admin")
    def del_student(i):
        for t in ("attendance", "marks", "submissions", "alerts", "messages", "leaves"): run(f"delete from {t} where student_id=?", (i,))
        run("delete from users where student_id=?", (i,)); run("delete from students where id=?", (i,)); flash("Student removed."); return redirect("/students")

    @app.route("/users")
    @need("admin")
    def users(): return render_template("users.html", rows=q("select u.*, s.name sname, s.sem ssem from users u left join students s on s.id=u.student_id order by u.role, u.id"), students=q("select * from students order by sem, name"))

    @app.route("/users/add", methods=["POST"])
    @need("admin")
    def add_faculty():
        f = request.form
        try: add_user(f["name"], f["email"], f["password"], "faculty", subject=f["subject"], sems=clean(f["sems"])); flash("Faculty account created.")
        except sqlite3.IntegrityError: flash("That email is already in use.")
        return redirect("/users")

    @app.route("/users/addparent", methods=["POST"])
    @need("admin")
    def add_parent():
        f = request.form
        try: add_user(f["name"], f["email"], f["password"], "parent", f["phone"], f["lang"], f["student_id"]); flash("Parent login created.")
        except sqlite3.IntegrityError: flash("That email is already in use.")
        return redirect("/users")

    @app.route("/users/save/<int:i>", methods=["POST"])
    @need("admin")
    def save_user(i):
        f = request.form; old = q("select name, role from users where id=?", (i,), True); nm = f["name"].strip()
        try:
            run("update users set name=?, email=?, password=?, plain=? where id=?", (nm, f["email"].strip().lower(), h(f["password"]), f["password"], i))
            if "sems" in f and old["role"] == "faculty": run("update users set sems=? where id=?", (clean(f["sems"]), i))
            if old["role"] == "faculty" and old["name"] != nm:
                run("update timetable set faculty=? where faculty=?", (nm, old["name"])); run("update messages set sender=? where sender=? and faculty_id=?", (nm, old["name"], i))
            flash("User details updated.")
        except sqlite3.IntegrityError: flash("That email is already in use.")
        return redirect("/users")

    @app.route("/users/advisor/<int:i>", methods=["POST"])
    @need("admin")
    def set_advisor(i):
        sem = int(request.form["sem"])
        run("update users set is_advisor=0, adv_sem=null where adv_sem=? or id=?", (sem, i))
        run("update users set is_advisor=1, adv_sem=?, sems=case when (',' || sems || ',') like ? then sems else trim(sems || ',' || ?, ',') end where id=? and role='faculty'", (sem, like(sem), sem, i))
        flash(f"Class advisor of {ordn(sem)} changed."); return redirect("/users")

    @app.route("/users/delete/<int:i>", methods=["POST"])
    @need("admin")
    def del_faculty(i): run("delete from users where id=? and role='faculty'", (i,)); flash("Faculty removed."); return redirect("/users")

    @app.route("/report.csv")
    @need(*STAFF)
    def report():
        o = io.StringIO(); w = csv.writer(o); w.writerow(["Name", "Roll", "Semester", "Attendance %", "Avg score", "Predicted final", "Status"])
        for s in q("select * from students where sem=?", (cur_sem(),)):
            a = analyse(s); w.writerow([s["name"], s["roll"], s["sem"], a["att"], a["avg"], a["pred"], "At risk" if a["risk"] else "On track"])
        return Response(o.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=class_report.csv"})
