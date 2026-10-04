import ml, ai_summary
from flask import request, session, jsonify
CHAT = {}

def today_att(q, sem):
    r = q("select s.name, a.present from attendance a join students s on s.id=a.student_id where a.date=date('now') and s.sem=? order by s.name", (sem,))
    return dict(p=[x["name"] for x in r if x["present"]], a=[x["name"] for x in r if not x["present"]], marked=bool(r))

def insights(q, s, a, subj, th):
    i = (s["id"],); out = []
    rec = [r["present"] for r in q("select present from attendance where student_id=? order by date desc limit 28", i)]
    if len(rec) >= 28:
        r1, r0 = sum(rec[:14]) / 14 * 100, sum(rec[14:]) / 14 * 100
        out.append((f"Attendance is {'improving' if r1 >= r0 else 'falling'}: {r1:.0f}% in the last 2 weeks vs {r0:.0f}% before.", r1 >= r0))
    ex = q("select exam, avg(score) v from marks where student_id=? group by exam order by exam", i)
    if len(ex) > 1:
        d = ex[-1]["v"] - ex[0]["v"]; out.append((f"Marks changed by {d:+.0f} from {ex[0]['exam']} to {ex[-1]['exam']}.", d >= 0))
    if subj:
        lo, hi = min(subj, key=lambda x: x[1]), max(subj, key=lambda x: x[1])
        out.append((f"Strongest subject: {hi[0]} ({hi[1]}). Needs work: {lo[0]} ({lo[1]}).", lo[1] >= 50))
    out.append(("Assignments are usually on time." if a["late"] <= 0 else f"Assignments are about {a['late']} days late on average.", a["late"] <= 0))
    return out

def drops(q, sem):
    out = []
    for s in q("select * from students where sem=?", (sem,)):
        rec = [r["present"] for r in q("select present from attendance where student_id=? order by date desc limit 28", (s["id"],))]
        if len(rec) >= 28:
            d = sum(rec[:14]) / 14 * 100 - sum(rec[14:]) / 14 * 100
            if d <= -15: out.append((s["name"], round(d)))
    return sorted(out, key=lambda x: x[1])

def fallback(qn, s, a, subj, th):
    t = qn.lower(); lo = min(subj, key=lambda x: x[1]) if subj else ("-", 0)
    if any(k in t for k in ("attend", "absent", "present")):
        return f"{s['name']}'s attendance is {a['att']}% (minimum {th}%). " + ("It is below the limit, so every missed class matters now." if a["att"] < th else "That is safe. Keep it above the limit.")
    if any(k in t for k in ("subject", "weak", "improve", "marks", "score")):
        return f"The weakest subject is {lo[0]} at {lo[1]}; the overall average is {a['avg']}. Revise {lo[0]} for 45 minutes daily and ask faculty for practice papers."
    if any(k in t for k in ("pass", "final", "predict", "result", "exam")):
        return f"The model predicts a final score of {a['pred']}/100. " + ("That is in the risk zone, so start support now." if a["risk"] else "That looks safe if the current pace continues.")
    if "assign" in t: return f"Assignments are {a['late']} days late on average (negative means early). Submitting on time protects the final score."
    return f"{s['name']}: attendance {a['att']}%, average {a['avg']}, predicted final {a['pred']}. Ask me about attendance, weak subjects, the exam forecast or assignments."

def register(app, q, analyse, need, THRESH, allowed_sems):
    def me():
        u = q("select * from users where id=?", (session["uid"],), True); s = q("select * from students where id=?", (u["student_id"],), True)
        subj = [[r["subject"], round(r["v"])] for r in q("select subject, avg(score) v from marks where student_id=? group by subject", (s["id"],))]
        return u, s, analyse(s), subj

    @app.route("/api/coach", methods=["POST"])
    @need("parent")
    def coach():
        u, s, a, subj = me(); qn = (request.get_json(silent=True) or {}).get("q", "").strip()[:300]; h = CHAT.setdefault(u["id"], [])
        rec = [r["present"] for r in q("select present from attendance where student_id=? order by date desc limit 7", (s["id"],))]
        hist = "\n".join(f"{'Parent' if r == 'me' else 'Coach'}: {t}" for r, t in h[-6:])
        p = (f"You are a warm, practical academic coach for the parent of {s['name']} (5th sem CSE). Reply in {u['lang']} unless the parent writes in another language; max 90 words; use the data, give one concrete next step. "
             f"Data: attendance {a['att']}% (minimum {THRESH}%), last 7 days present {sum(rec)}/{len(rec)}, average score {a['avg']}, predicted final {a['pred']}, at risk: {a['risk']}, "
             f"subject averages {subj}, assignments {a['late']} days late on average.\nConversation so far:\n{hist}\nParent: {qn}\nCoach:")
        ans = ai_summary.gemini(p, fallback(qn, s, a, subj, THRESH)); h += [("me", qn), ("ai", ans)]; del h[:-12]
        return jsonify(a=ans)

    @app.route("/api/coach/clear", methods=["POST"])
    @need("parent")
    def clear(): CHAT[session["uid"]] = []; return jsonify(ok=1)

    @app.route("/api/goal")
    @need("parent")
    def goal():
        u, s, a, subj = me(); t = float(request.args.get("target", 60)); at, av, la = a["att"], a["avg"], a["late"]
        if ml.predict(at, av, la) >= t: return jsonify(text=f"Already on track: the predicted score {a['pred']} meets your target of {t:.0f}.")
        na = next((x for x in range(int(at), 101) if ml.predict(x, av, la) >= t), None)
        nv = next((x for x in range(int(av), 101) if ml.predict(at, x, la) >= t), None)
        nb = next((x for x in range(int(at), 101) if ml.predict(x, min(100, av + 10), la) >= t), None)
        o = [f"Raise attendance from {at}% to {na}%" if na else None, f"Raise the average score from {av} to {nv}" if nv else None,
             f"Or gain 10 average marks and reach {nb}% attendance" if nb else None]
        return jsonify(text=f"To reach {t:.0f}/100: " + "; ".join(x for x in o if x) + "." if any(o) else f"{t:.0f} is out of reach with these factors alone. Try a lower target.")

    @app.route("/api/intervention/<int:sid>")
    @need("admin", "faculty")
    def intervention(sid):
        s = q("select * from students where id=?", (sid,), True)
        if not s or s["sem"] not in allowed_sems(): return jsonify(lines=[]), 403
        a = analyse(s)
        subj = [[r["subject"], round(r["v"])] for r in q("select subject, avg(score) v from marks where student_id=? group by subject", (sid,))]
        weak = min(subj, key=lambda x: x[1])[0] if subj else "core subjects"
        fb = [x for x in [f"Meet {s['name']} and the parents this week to discuss attendance ({a['att']}%)." if a["att"] < THRESH else None,
              f"Arrange extra classes or practice papers for {weak}.", "Set assignment deadlines with reminders." if a["late"] > 2 else None, "Review progress again in two weeks."] if x]
        p = (f"You are an academic counsellor. Give a 4-step early-intervention plan for {s['name']}: attendance {a['att']}%, average {a['avg']}, predicted final {a['pred']}, "
             f"weakest subject {weak}, assignments {a['late']} days late. One short line per step, no numbering, no extra text.")
        import ai_summary as g
        return jsonify(lines=[l.strip("-•* 0123456789.") for l in g.gemini(p, "\n".join(fb)).split("\n") if l.strip()][:5])

    @app.route("/api/draft/<int:mid>")
    @need("admin", "faculty")
    def draft(mid):
        m = q("select m.*, s.name sname from messages m join students s on s.id=m.student_id where m.rowid=?", (mid,), True)
        if not m or (session["role"] != "admin" and m["faculty_id"] != session["uid"]): return jsonify(text=""), 403
        p = f"Write a polite 2-3 sentence reply from a college faculty member to this message from the parent of {m['sname']}: \"{m['body']}\". Output only the reply."
        return jsonify(text=ai_summary.gemini(p, f"Hello, thank you for your message about {m['sname']}. I will look into this and get back to you shortly."))
