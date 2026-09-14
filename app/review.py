"""The weekly review: turns stored people, threads and events into a short
list of things that want attention this week.

Three signals, in priority order:

  dated    an event (or birthday) has entered its lead time
  quiet    an open thread has had nothing written against it in a while
  drift    a person has had nothing written about them in a long while

The last two are the cadence replacement. Nothing is configured per person;
staleness is inferred from your own writing activity.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from .db import get_settings


def _safe_date(year: int, month: int, day: int) -> date:
    """Feb 29 in a non-leap year lands on Feb 28 rather than blowing up."""
    while day > 28:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)


def _next_occurrence(month: int, day: int, today: date) -> date:
    this_year = _safe_date(today.year, month, day)
    if this_year >= today:
        return this_year
    return _safe_date(today.year + 1, month, day)


# How each repeat advances: by whole days, or by whole months (which clamp to
# the end of a short month — the 31st becomes the 28th in February, and then
# back to the 31st in March, because every step is measured from the anchor).
STEP_DAYS = {"daily": 1, "weekly": 7, "biweekly": 14}
STEP_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}

# Roughly how far apart two occurrences are. Used to stop a short repeat from
# sitting in the review permanently: a lead time is capped just under its own
# interval, so a daily date appears on the day rather than every day.
INTERVAL_DAYS = {"daily": 1, "weekly": 7, "biweekly": 14, "monthly": 28, "quarterly": 89}


def _add_months(anchor: date, months: int) -> date:
    total = anchor.month - 1 + months
    return _safe_date(anchor.year + total // 12, total % 12 + 1, anchor.day)


def next_occurrence(anchor: date, recurrence: str, today: date) -> date | None:
    """When this event next falls, or None if it is a one-off already past."""
    if recurrence not in STEP_DAYS and recurrence not in STEP_MONTHS:
        return anchor if anchor >= today else None
    if anchor >= today:
        return anchor

    if recurrence in STEP_DAYS:
        step = STEP_DAYS[recurrence]
        elapsed = (today - anchor).days
        return anchor + timedelta(days=-(-elapsed // step) * step)

    step = STEP_MONTHS[recurrence]
    months = (today.year - anchor.year) * 12 + (today.month - anchor.month)
    n = max(0, (months // step) * step)
    candidate = _add_months(anchor, n)
    while candidate < today:
        n += step
        candidate = _add_months(anchor, n)
    return candidate


def effective_lead(recurrence: str, lead_days: int) -> int:
    """Never let a lead time reach its own repeat interval, or the item would
    be showing every single day it exists."""
    interval = INTERVAL_DAYS.get(recurrence)
    return lead_days if interval is None else min(lead_days, interval - 1)


def _days_word(n: int) -> str:
    if n == 0:
        return "today"
    if n == 1:
        return "tomorrow"
    return f"in {n} days"


def _stale_word(days: int | None) -> str:
    if days is None:
        return "nothing written yet"
    if days < 60:
        return f"{days} days ago"
    months = days // 30
    return f"about {months} months ago"


def build_review(conn: sqlite3.Connection, today: date | None = None) -> dict:
    today = today or date.today()
    settings = get_settings(conn)
    birthday_lead = int(settings["birthday_lead_days"])
    thread_quiet = int(settings["thread_quiet_days"])
    person_quiet = int(settings["person_quiet_days"])
    horizon = int(settings["review_horizon_days"])

    dismissed = {
        r["key"]
        for r in conn.execute(
            "SELECT key FROM dismissal WHERE snooze_until >= ?", (today.isoformat(),)
        )
    }

    people = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT * FROM person WHERE archived = 0")
    }

    # Last time anything was written about each person, and against each thread.
    last_entry_person = {
        r["person_id"]: r["last"]
        for r in conn.execute(
            "SELECT person_id, MAX(occurred_on) AS last FROM entry GROUP BY person_id"
        )
    }
    last_entry_thread = {
        r["thread_id"]: r["last"]
        for r in conn.execute(
            "SELECT thread_id, MAX(occurred_on) AS last FROM entry "
            "WHERE thread_id IS NOT NULL GROUP BY thread_id"
        )
    }

    threads = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT * FROM thread WHERE status = 'open'")
    }

    items: list[dict] = []

    # --- dated: explicit events -------------------------------------------
    for row in conn.execute("SELECT * FROM event"):
        event = dict(row)
        person = people.get(event["person_id"])
        if person is None:
            continue

        anchor = date.fromisoformat(event["on_date"])
        recurrence = event["recurrence"]

        # done_at retires a one-off for good. A repeat is never "finished", so
        # a handled occurrence is cleared through the dismissal table instead.
        if recurrence == "none" and event["done_at"]:
            continue

        occurrence = next_occurrence(anchor, recurrence, today)
        if occurrence is None:
            continue

        days_until = (occurrence - today).days
        lead = effective_lead(recurrence, max(event["lead_days"], 0))
        if days_until > min(lead, horizon):
            continue

        thread = threads.get(event["thread_id"]) if event["thread_id"] else None
        context = event["notes"] or ""
        if thread:
            context = (
                f"Open thread: {thread['title']}. " + context
            ).strip()

        items.append(
            {
                "key": f"event:{event['id']}:{occurrence.isoformat()}",
                "kind": "dated",
                "person_id": person["id"],
                "person_name": person["name"],
                "title": event["title"],
                "context": context,
                "date": occurrence.isoformat(),
                "days_until": days_until,
                "when": _days_word(days_until),
                "event_id": event["id"],
                "recurrence": recurrence,
                "thread_id": event["thread_id"],
            }
        )

    # --- dated: birthdays, derived from the person record -----------------
    for person in people.values():
        if not person["birth_month"] or not person["birth_day"]:
            continue
        occurrence = _next_occurrence(person["birth_month"], person["birth_day"], today)
        days_until = (occurrence - today).days
        if days_until > min(birthday_lead, horizon):
            continue

        context = ""
        if person["birth_year"]:
            context = f"Turning {occurrence.year - person['birth_year']}."

        items.append(
            {
                "key": f"birthday:{person['id']}:{occurrence.isoformat()}",
                "kind": "dated",
                "person_id": person["id"],
                "person_name": person["name"],
                "title": f"{person['name']}'s birthday",
                "context": context,
                "date": occurrence.isoformat(),
                "days_until": days_until,
                "when": _days_word(days_until),
                "event_id": None,
                "recurrence": "yearly",
                "thread_id": None,
            }
        )

    # --- quiet: open threads nobody has touched ---------------------------
    for thread in threads.values():
        person = people.get(thread["person_id"])
        if person is None:
            continue

        last = last_entry_thread.get(thread["id"]) or thread["created_at"][:10]
        silent_days = (today - date.fromisoformat(last)).days
        if silent_days < thread_quiet:
            continue

        items.append(
            {
                "key": f"thread:{thread['id']}:{today.isoformat()}",
                "kind": "quiet",
                "person_id": person["id"],
                "person_name": person["name"],
                "title": thread["title"],
                "context": f"Open thread, last touched {_stale_word(silent_days)}.",
                "date": None,
                "days_until": None,
                "silent_days": silent_days,
                "event_id": None,
                "thread_id": thread["id"],
            }
        )

    # --- drift: people who have gone quiet --------------------------------
    people_with_open_threads = {t["person_id"] for t in threads.values()}
    for person in people.values():
        # Someone with an open thread is already surfacing above; don't double up.
        if person["id"] in people_with_open_threads:
            continue

        last = last_entry_person.get(person["id"])
        reference = last or person["created_at"][:10]
        silent_days = (today - date.fromisoformat(reference)).days
        if silent_days < person_quiet:
            continue

        items.append(
            {
                "key": f"person:{person['id']}:{today.isoformat()}",
                "kind": "drift",
                "person_id": person["id"],
                "person_name": person["name"],
                "title": f"You haven't written about {person['name']} in a while",
                "context": f"Last note {_stale_word(silent_days if last else None)}.",
                "date": None,
                "days_until": None,
                "silent_days": silent_days,
                "event_id": None,
                "thread_id": None,
            }
        )

    items = [i for i in items if i["key"] not in dismissed]

    bucket = {"dated": 0, "quiet": 1, "drift": 2}
    items.sort(
        key=lambda i: (
            bucket[i["kind"]],
            i["days_until"] if i["days_until"] is not None else 0,
            -(i.get("silent_days") or 0),
            i["person_name"].lower(),
        )
    )

    return {
        "generated_on": today.isoformat(),
        "items": items,
        "counts": {
            "dated": sum(1 for i in items if i["kind"] == "dated"),
            "quiet": sum(1 for i in items if i["kind"] == "quiet"),
            "drift": sum(1 for i in items if i["kind"] == "drift"),
        },
    }


def dismiss(conn: sqlite3.Connection, key: str, days: int, today: date | None = None) -> None:
    """Hide one review item for `days`. Keys carry their occurrence date, so
    snoozing this year's birthday never hides next year's."""
    today = today or date.today()
    until = (today + timedelta(days=max(days, 1))).isoformat()
    conn.execute(
        "INSERT INTO dismissal (key, snooze_until, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET snooze_until = excluded.snooze_until",
        (key, until, today.isoformat()),
    )
