import datetime as dt
from flask import request, session, render_template, jsonify, redirect
import ml, ai_summary, ai2
from ai2 import CHAT

def register(app, q, run, analyse, need, THRESH, cur_sem):
    one = lambda sql, a=(): q(sql, a, True)
    def ctx():
        u = one("select * from users where id=?", (session["uid"],)); s = one("select * from students where id=?", (u["student_id"],))
        subj = [[r["subject"], round(r["v"])] for r in q("select subject, avg(score) v from marks where student_id=? group by subject", (s["id"],))]
        return u, s, analyse(s), subj, (min(subj, key=lambda x: x[1])[0] if subj else "-")

    @app.route("/parent")
    @need("parent")
    def parent():
        u, s, a, subj, weak = ctx(); i = (s["id"],)
        allp = sorted([analyse(x)["pred"] for x in q("select * from students where sem=?", (s["sem"],))], reverse=True)
        d = dt.date.today().strftime("%a"); d = d if d in ("Mon", "Tue", "Wed", "Thu", "Fri") else "Mon"
        return render_template("parent.html", s=s, a=a, u=u, lang=u["lang"], text=ai_summary.summary(s["name"], a, u["lang"]), subj=subj, weak=weak,
            att=[[r["w"], round(r["v"])] for r in q("select strftime('%W',date) w, avg(present)*100 v from attendance where student_id=? group by w order by w", i)],
            rank=allp.index(a["pred"]) + 1, total=len(allp), today=d, thresh=THRESH, tatt=ai2.today_att(q, s["sem"]), ins=ai2.insights(q, s, a, subj, THRESH),
            heat=[r["present"] for r in q("select present from (select present, date from attendance where student_id=? order by date desc limit 42) order by date", i)],
            classes=q("select * from timetable where day=? and sem=?", (d, s["sem"])), marks=q("select * from marks where student_id=?", i),
            subs=q("select * from submissions where student_id=?", i), news=q("select * from announcements where sem=? order by rowid desc limit 3", (s["sem"],)),
            notes=q("select * from alerts where student_id=? order by rowid desc limit 3", i),
            leaves=q("select * from leaves where student_id=? order by rowid desc limit 2", i))

    @app.route("/api/plan")
    @need("parent")
    def plan():
        u, s, a, subj, weak = ctx()
        fb = "\n".join([f"Give extra revision time to {weak} every day.", f"Attend every class and keep attendance above {THRESH}%.",
                        "Submit assignments before the due date.", "Solve one previous paper each weekend.", "Meet the faculty if any topic is unclear."])
        p = (f"Write a 5-line weekly study plan in {u['lang']} for a student. Weakest subject: {weak}. Attendance {a['att']}%, average score {a['avg']}, "
             f"assignments {a['late']} days late on average. One short actionable line each, no numbering, no extra text.")
        return jsonify(lines=[l.strip("-•* 0123456789.") for l in ai_summary.gemini(p, fb).split("\n") if l.strip()][:6])

    @app.route("/api/predict")
    @need("parent", "admin", "faculty")
    def predict():
        at, av, la = (float(request.args[k]) for k in ("att", "avg", "late"))
        p = ml.predict(at, av, la); return jsonify(pred=p, risk=p < 40 or at < THRESH)

    @app.route("/assistant", methods=["GET", "POST"])
    @need("parent")
    def assistant():
        u, s, a, subj, weak = ctx(); h = CHAT.setdefault(u["id"], [])
        if request.method == "POST" and request.form["q"].strip():
            qn = request.form["q"].strip()
            fb = (f"{s['name']} has {a['att']}% attendance, an average score of {a['avg']} and a predicted final score of {a['pred']}. "
                  f"The weakest subject is {weak}. Focus revision there and keep attendance above {THRESH}%. (Add a Gemini key for detailed AI answers.)")
            p = (f"You are a friendly academic coach speaking to the parent of {s['name']}. Reply in {u['lang']}, under 80 words. Data: attendance {a['att']}%, "
                 f"average score {a['avg']}, predicted final score {a['pred']}, subject averages {subj}, assignments {a['late']} days late on average. Question: {qn}")
            h += [("me", qn), ("ai", ai_summary.gemini(p, fb))]; del h[:-12]
            return redirect("/assistant")
        return render_template("assistant.html", chat=h, weak=weak)

    @app.route("/staff")
    @need("admin", "faculty")
    def staff():
        sem = cur_sem(); st = q("select * from students where sem=?", (sem,)); rows = [(s, analyse(s)) for s in st]
        return render_template("staff.html", rows=rows, students=st, worst=sorted(rows, key=lambda r: r[1]["pred"])[:4],
            best=sorted(rows, key=lambda r: -r[1]["pred"])[:4], imp=ml.importance(), tatt=ai2.today_att(q, sem), drops=ai2.drops(q, sem), pend=one("select count(*) c from leaves l join students s on s.id=l.student_id where l.status='Pending' and s.sem=?", (sem,))["c"],
            log=q("select a.*, s.name from alerts a join students s on s.id=a.student_id where s.sem=? order by a.rowid desc limit 6", (sem,)),
            msgs=q("select m.*, s.name from messages m join students s on s.id=m.student_id where (?='admin' or m.faculty_id=?) and s.sem=? order by m.rowid desc limit 4", (session["role"], session["uid"], sem)))

    @app.route("/api/insight")
    @need("admin", "faculty")
    def insight():
        r = [(s["name"], analyse(s)) for s in q("select * from students")]; r = [(n, a) for n, a in r if a["risk"]]
        fb = (f"{len(r)} student(s) are at risk: " + ", ".join(n for n, _ in r) + ". Hold a short counselling session with them this week and alert their parents.") if r else "No student is at risk right now."
        p = ("You advise college faculty. In 3 short sentences, summarise this class and recommend actions. At-risk students: "
             + "; ".join(f"{n} (attendance {a['att']}%, avg {a['avg']}, predicted {a['pred']})" for n, a in r))
        return jsonify(text=ai_summary.gemini(p, fb))
