"""Smoke tests for the review engine. Plain python, no test runner needed:

    python tests/test_review.py
"""

import sys
import sqlite3
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import MIGRATIONS
from app.review import build_review, dismiss, _next_occurrence, _safe_date

TODAY = date(2026, 6, 15)
FAILURES = []


def fresh_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    for script in MIGRATIONS:
        conn.executescript(script)
    return conn


def add_person(conn, name, **kw):
    stamp = kw.pop("created_at", TODAY.isoformat())
    cols = {
        "name": name, "relationship": "", "birth_year": None, "birth_month": None,
        "birth_day": None, "location": "", "basics": "", "character_notes": "",
        "archived": 0, "created_at": stamp, "updated_at": stamp,
    }
    cols.update(kw)
    keys = ", ".join(cols)
    marks = ", ".join("?" * len(cols))
    return conn.execute(
        f"INSERT INTO person ({keys}) VALUES ({marks})", tuple(cols.values())
    ).lastrowid


def add_thread(conn, person_id, title, created_at=TODAY.isoformat(), status="open"):
    return conn.execute(
        "INSERT INTO thread (person_id, title, detail, status, created_at, updated_at) "
        "VALUES (?, ?, '', ?, ?, ?)",
        (person_id, title, status, created_at, created_at),
    ).lastrowid


def add_entry(conn, person_id, on, thread_id=None):
    conn.execute(
        "INSERT INTO entry (person_id, thread_id, body, occurred_on, created_at) "
        "VALUES (?, ?, 'note', ?, ?)",
        (person_id, thread_id, on, on),
    )


def add_event(conn, person_id, title, on, recurrence="none", lead_days=7, thread_id=None):
    return conn.execute(
        "INSERT INTO event (person_id, thread_id, title, on_date, recurrence, lead_days, notes, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, '', ?)",
        (person_id, thread_id, title, on, recurrence, lead_days, TODAY.isoformat()),
    ).lastrowid


def check(label, condition):
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILURES.append(label)


def keys(review):
    return {i["key"].split(":")[0] for i in review["items"]}


def titles(review):
    return [i["title"] for i in review["items"]]


# --- date maths -----------------------------------------------------------

print("date handling")
check("Feb 29 falls back to Feb 28 in a common year", _safe_date(2027, 2, 29) == date(2027, 2, 28))
check("a birthday later this year stays this year",
      _next_occurrence(12, 25, TODAY) == date(2026, 12, 25))
check("a birthday already passed rolls to next year",
      _next_occurrence(1, 3, TODAY) == date(2027, 1, 3))
check("a birthday today counts as today",
      _next_occurrence(6, 15, TODAY) == date(2026, 6, 15))

# --- birthdays ------------------------------------------------------------

print("\nbirthdays")
conn = fresh_db()
soon = TODAY + timedelta(days=10)
far = TODAY + timedelta(days=40)
add_person(conn, "Priya", birth_month=soon.month, birth_day=soon.day, birth_year=1990)
add_person(conn, "Sam", birth_month=far.month, birth_day=far.day)
review = build_review(conn, TODAY)
check("a birthday inside the lead window surfaces", "Priya's birthday" in titles(review))
check("a birthday outside it does not", "Sam's birthday" not in titles(review))
check("age is computed from the birth year",
      any("Turning 36" in i["context"] for i in review["items"]))

# --- events ---------------------------------------------------------------

print("\nevents")
conn = fresh_db()
mom = add_person(conn, "Mom", created_at=TODAY.isoformat())
add_event(conn, mom, "Cardiology", (TODAY + timedelta(days=5)).isoformat(), lead_days=7)
add_event(conn, mom, "Dentist", (TODAY + timedelta(days=30)).isoformat(), lead_days=7)
done_id = add_event(conn, mom, "Old scan", (TODAY + timedelta(days=2)).isoformat())
conn.execute("UPDATE event SET done_at = ? WHERE id = ?", (TODAY.isoformat(), done_id))
add_event(conn, mom, "Past appt", (TODAY - timedelta(days=3)).isoformat())
review = build_review(conn, TODAY)
check("an event inside its lead time surfaces", "Cardiology" in titles(review))
check("an event beyond its lead time waits", "Dentist" not in titles(review))
check("an event marked done disappears", "Old scan" not in titles(review))
check("a past one-off disappears", "Past appt" not in titles(review))

print("\nthread context on events")
conn = fresh_db()
mom = add_person(conn, "Mom")
thread = add_thread(conn, mom, "Managing her heart condition")
add_event(conn, mom, "Cardiology", (TODAY + timedelta(days=4)).isoformat(), thread_id=thread)
review = build_review(conn, TODAY)
item = next(i for i in review["items"] if i["title"] == "Cardiology")
check("an event linked to a thread carries its context",
      "Managing her heart condition" in item["context"])
check("the linked thread does not also emit its own quiet item",
      len(review["items"]) == 1)

# --- quiet threads --------------------------------------------------------

print("\nquiet threads")
conn = fresh_db()
dad = add_person(conn, "Dad")
stale = add_thread(conn, dad, "Job situation", created_at=(TODAY - timedelta(days=60)).isoformat())
add_entry(conn, dad, (TODAY - timedelta(days=30)).isoformat(), thread_id=stale)
active = add_thread(conn, dad, "House move", created_at=(TODAY - timedelta(days=60)).isoformat())
add_entry(conn, dad, (TODAY - timedelta(days=2)).isoformat(), thread_id=active)
review = build_review(conn, TODAY)
check("a thread with no recent note surfaces", "Job situation" in titles(review))
check("a recently touched thread stays quiet", "House move" not in titles(review))

print("\nclosed threads")
conn = fresh_db()
p = add_person(conn, "Ana")
add_thread(conn, p, "Resolved thing",
           created_at=(TODAY - timedelta(days=200)).isoformat(), status="closed")
review = build_review(conn, TODAY)
check("a closed thread never surfaces", "Resolved thing" not in titles(review))

# --- drift ----------------------------------------------------------------

print("\ndrift")
conn = fresh_db()
old = (TODAY - timedelta(days=200)).isoformat()
arun = add_person(conn, "Arun", created_at=old)
add_entry(conn, arun, (TODAY - timedelta(days=150)).isoformat())
recent = add_person(conn, "Leah", created_at=old)
add_entry(conn, recent, (TODAY - timedelta(days=5)).isoformat())
threaded = add_person(conn, "Nina", created_at=old)
add_thread(conn, threaded, "Something open", created_at=TODAY.isoformat())
review = build_review(conn, TODAY)
check("a long-silent person surfaces", any("Arun" in t for t in titles(review)))
check("a recently noted person does not", not any("Leah" in t for t in titles(review)))
check("someone with an open thread isn't also flagged as drifting",
      not any("haven't written about Nina" in t for t in titles(review)))

print("\narchiving")
conn = fresh_db()
gone = add_person(conn, "Ex", created_at=(TODAY - timedelta(days=300)).isoformat(), archived=1)
add_event(conn, gone, "Birthday lunch", (TODAY + timedelta(days=2)).isoformat())
review = build_review(conn, TODAY)
check("an archived person is fully excluded", review["items"] == [])

# --- dismissal ------------------------------------------------------------

print("\nsnoozing")
conn = fresh_db()
# 12 days out, so the birthday is still ahead when the snooze lapses in 7.
bday = TODAY + timedelta(days=12)
pid = add_person(conn, "Priya", birth_month=bday.month, birth_day=bday.day)
review = build_review(conn, TODAY)
key = review["items"][0]["key"]
dismiss(conn, key, 7, TODAY)
check("a snoozed item is hidden", build_review(conn, TODAY)["items"] == [])
check("it comes back after the snooze",
      "Priya's birthday" in titles(build_review(conn, TODAY + timedelta(days=8))))
check("a passed birthday does not linger",
      "Priya's birthday" not in titles(build_review(conn, TODAY + timedelta(days=20))))
check("snoozing this year's birthday never hides next year's",
      "Priya's birthday" in titles(build_review(conn, date(2027, 6, 20))))

# --- ordering -------------------------------------------------------------

print("\nordering")
conn = fresh_db()
a = add_person(conn, "Later", created_at=TODAY.isoformat())
b = add_person(conn, "Sooner", created_at=TODAY.isoformat())
c = add_person(conn, "Quiet", created_at=(TODAY - timedelta(days=300)).isoformat())
add_event(conn, a, "Later thing", (TODAY + timedelta(days=6)).isoformat())
add_event(conn, b, "Sooner thing", (TODAY + timedelta(days=1)).isoformat())
review = build_review(conn, TODAY)
check("dated items lead, soonest first", titles(review)[:2] == ["Sooner thing", "Later thing"])
check("drift sinks to the bottom", review["items"][-1]["kind"] == "drift")

# --- settings -------------------------------------------------------------

print("\nsettings")
conn = fresh_db()
conn.execute("INSERT INTO setting (key, value) VALUES ('birthday_lead_days', '3')")
bday = TODAY + timedelta(days=10)
add_person(conn, "Priya", birth_month=bday.month, birth_day=bday.day)
check("a shorter lead time suppresses a further-out birthday",
      build_review(conn, TODAY)["items"] == [])

print("\nhorizon")
conn = fresh_db()
conn.execute("INSERT INTO setting (key, value) VALUES ('review_horizon_days', '5')")
p = add_person(conn, "Mom")
add_event(conn, p, "Far thing", (TODAY + timedelta(days=20)).isoformat(), lead_days=60)
check("the horizon caps a generous per-event lead time",
      build_review(conn, TODAY)["items"] == [])

print()
if FAILURES:
    print(f"{len(FAILURES)} failed:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("all passed")
