import sqlite3, random
from werkzeug.security import generate_password_hash as h
import config
random.seed(3)
c = sqlite3.connect(config.DB_PATH)
for t in "users students attendance marks submissions announcements alerts timetable messages leaves".split():
    c.execute(f"drop table if exists {t}")
c.executescript("""
create table users(id integer primary key, name, email unique, password, plain, role, phone, lang, student_id integer, subject, is_advisor integer default 0, adv_sem integer, sems default '');
create table students(id integer primary key, name, roll, class, sem integer);
create table attendance(student_id integer, date, present integer);
create unique index ux_att on attendance(student_id, date);
create table marks(student_id integer, subject, exam, score integer);
create table submissions(student_id integer, title, days_late integer);
create table announcements(sem integer, title, body, date default current_date);
create table alerts(student_id integer, channel, message, status, date default current_timestamp);
create table timetable(sem integer, day, time, subject, faculty);
create table messages(student_id integer, sender, body, date default current_timestamp, faculty_id integer, parent_id integer);
create table leaves(id integer primary key, student_id integer, reason, from_date, to_date, status default 'Pending', reviewed_by, reviewed_on);
""")
def U(name, email, pw, role, phone=None, lang=None, sid=None, subject=None, adv=None, sems=""):
    c.execute("insert into users(name,email,password,plain,role,phone,lang,student_id,subject,is_advisor,adv_sem,sems) values(?,?,?,?,?,?,?,?,?,?,?,?)",
              (name, email, h(pw), pw, role, phone, lang, sid, subject, 1 if adv else 0, adv, sems))
ordn = lambda n: f"{n}{'st' if n == 1 else 'nd' if n == 2 else 'rd' if n == 3 else 'th'} Sem"
U("Admin", "admin@demo.com", "admin123", "admin")
FN = "Nair Rao Bhat Kulkarni Shetty Hegde Joshi Menon Pillai Naik Gupta Das".split()
SUB = ["Maths", "Physics", "DBMS", "OS"]
for i, n in enumerate(FN, 1):
    adv = i if i <= 8 else None
    U(f"Prof. {n}", f"{n.lower()}@demo.com", f"{n.lower()}@fac{i}", "faculty", subject=SUB[i % 4], adv=adv,
      sems=str(i) if adv else f"{(i - 8)},{(i - 8) + 4}")
FIRST = "Aarav Diya Karthik Sneha Rohan Ananya Vikram Meera Arjun Kavya Imran Pooja Nikhil Riya Sahil Tara".split()
LAST = "Sharma Rao Iyer Reddy Mehta Gowda Singh Nair".split()
L = ["Hindi", "Kannada", "Tamil", "Telugu", "English", "Marathi"]
N = 0
for sem in range(1, 9):
    for k in range(4):
        i = N; N += 1; n = f"{FIRST[i % 16]} {LAST[(5 * i + i // 16) % 8]}"
        rate = random.uniform(.55, .97); base = rate * 100 - 10
        c.execute("insert into students values(?,?,?,?,?)", (N, n, f"{sem}BE{k + 1:02d}", f"{ordn(sem)} B.E", sem))
        U(f"Parent of {n}", f"parent{N}@demo.com", f"{n.split()[0].lower()}@{100 + N}", "parent", f"+9190000{N:05d}", L[N % 6], N)
        for d in range(42):
            c.execute("insert into attendance values(?,date('now',?),?)", (N, f"-{d} day", int(random.random() < rate)))
        for s in SUB:
            for e in ("Internal 1", "Internal 2", "Internal 3"):
                c.execute("insert into marks values(?,?,?,?)", (N, s, e, int(max(5, min(100, base + random.randint(-12, 12))))))
        for a in range(1, 6):
            c.execute("insert into submissions values(?,?,?)", (N, f"Assignment {a}", round(random.uniform(-1, 1) + (1 - rate) * 10)))
for sem in range(1, 9):
    for d in "Mon Tue Wed Thu Fri".split():
        for j, t in enumerate(["09:00", "10:00", "11:15", "13:00"]):
            c.execute("insert into timetable values(?,?,?,?,?)", (sem, d, t, SUB[(j + len(d)) % 4], f"Prof. {FN[sem - 1] if j % 2 == 0 else FN[8 + (sem - 1) % 4]}"))
    c.execute("insert into announcements(sem,title,body) values(?,?,?)", (sem, f"{ordn(sem)} internal schedule", "Internal 3 exams begin next Monday."))
c.execute("insert into messages(student_id,sender,body,faculty_id,parent_id) values(1,'Parent','Could you share the DBMS lab syllabus?',2,(select id from users where student_id=1))")
c.execute("insert into leaves(student_id,reason,from_date,to_date) values(2,'Fever, doctor advised rest','2026-10-05','2026-10-07')")
c.execute("insert into leaves(student_id,reason,from_date,to_date) values(17,'Family function','2026-10-09','2026-10-10')")
c.commit(); print("Database ready:", config.DB_PATH)
