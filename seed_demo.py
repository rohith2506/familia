"""Drop some example data in so the weekly review has something to show.

    .venv/bin/python seed_demo.py

Delete data/familia.db to start over empty.
"""
import os, sys
from datetime import date, timedelta

os.environ.setdefault("FAMILIA_DB", "data/familia.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db

db.migrate()
today = date.today()
conn = db.connect()

if conn.execute("SELECT COUNT(*) FROM person").fetchone()[0]:
    print("Already has people in it — not touching anything.")
    raise SystemExit

def person(**kw):
    stamp = kw.pop("created_at", today.isoformat())
    cols = dict(name="", relationship="", birth_year=None, birth_month=None, birth_day=None,
                location="", basics="", character_notes="", archived=0,
                created_at=stamp, updated_at=stamp)
    cols.update(kw)
    return conn.execute(
        f"INSERT INTO person ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        tuple(cols.values())).lastrowid

def thread(pid, title, detail="", created=None):
    stamp = (created or today).isoformat()
    return conn.execute(
        "INSERT INTO thread (person_id,title,detail,status,created_at,updated_at) "
        "VALUES (?,?,?,'open',?,?)", (pid, title, detail, stamp, stamp)).lastrowid

def entry(pid, body, days_ago, tid=None):
    on = (today - timedelta(days=days_ago)).isoformat()
    conn.execute("INSERT INTO entry (person_id,thread_id,body,occurred_on,created_at) "
                 "VALUES (?,?,?,?,?)", (pid, tid, body, on, on))

def event(pid, title, in_days, lead=7, notes="", tid=None, recurrence="none"):
    conn.execute(
        "INSERT INTO event (person_id,thread_id,title,on_date,recurrence,lead_days,notes,created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (pid, tid, title, (today + timedelta(days=in_days)).isoformat(),
         recurrence, lead, notes, today.isoformat()))

# A mother with a health situation — the thread carries the prognosis, the
# event carries the next appointment, the notes carry how she actually is.
bday = today + timedelta(days=184)
mom = person(name="Amma", relationship="mother", location="Hyderabad",
             birth_month=bday.month, birth_day=bday.day, birth_year=1958,
             basics="Lives with Nanna in the Kondapur flat. Retired schoolteacher.\n"
                    "Her sister Lakshmi visits on Sundays.",
             character_notes="Downplays how she is feeling — ask twice, and ask specifically.\n"
                             "Proud of managing on her own; offering help the wrong way lands badly.\n"
                             "Loves hearing about work in detail.")
heart = thread(mom, "Managing her heart condition",
               "Under Dr. Rao (cardiology) since March. Told to walk daily, cut salt, "
               "monitor BP at home. Prognosis good as long as she keeps to it.")
event(mom, "Cardiology follow-up with Dr. Rao", 6, lead=10, tid=heart,
      notes="Ask what he said about the walking, and whether the BP readings are where he wants them.")
entry(mom, "Called. Says she is fine but sounded tired. Pushed twice — turns out she is "
           "walking maybe 3 days a week, not daily. Didn't want to worry me.", 9, heart)
entry(mom, "Nanna says the new tablets are agreeing with her better than the last lot.", 22, heart)

# The friend whose birthday you don't want to miss again.
bday = today + timedelta(days=11)
person(name="Priya", relationship="close friend", location="Bangalore",
       birth_month=bday.month, birth_day=bday.day, birth_year=1991,
       basics="Married to Karthik. One daughter, Maya (4).",
       character_notes="Terrible at replying to texts, always glad when you call. Hates surprise parties.")

# A thread that has gone quiet.
dad = person(name="Nanna", relationship="father", location="Hyderabad",
             birth_month=11, birth_day=2, birth_year=1955)
knee = thread(dad, "Deciding about the knee surgery",
              "Orthopaedic said replacement is the long-term answer. He keeps putting it off.",
              created=today - timedelta(days=70))
entry(dad, "Still weighing it. Wants a second opinion before committing.", 41, knee)

# Someone you are quietly drifting from.
arun = person(name="Arun", relationship="friend from college", location="Seattle",
              created_at=(today - timedelta(days=400)).isoformat(),
              character_notes="Always the one who reaches out. Worth being the one who does it, for once.")
entry(arun, "Caught up over coffee when he was in town. Thinking about leaving the startup.", 194)

conn.close()
print("Seeded 4 people. Open the app — the review should have four items.")
