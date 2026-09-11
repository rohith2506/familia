"""SQLite storage. Single-user, single-file, no ORM."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("FAMILIA_DB", "data/familia.db"))

# Each entry is applied once, in order, and recorded via PRAGMA user_version.
# Append new migrations to the end; never edit one that has shipped.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE person (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        relationship    TEXT NOT NULL DEFAULT '',
        birth_year      INTEGER,
        birth_month     INTEGER,
        birth_day       INTEGER,
        location        TEXT NOT NULL DEFAULT '',
        basics          TEXT NOT NULL DEFAULT '',
        character_notes TEXT NOT NULL DEFAULT '',
        archived        INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    );

    CREATE TABLE thread (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id  INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
        title      TEXT NOT NULL,
        detail     TEXT NOT NULL DEFAULT '',
        status     TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        closed_at  TEXT
    );
    CREATE INDEX thread_person ON thread(person_id, status);

    CREATE TABLE entry (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id   INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
        thread_id   INTEGER REFERENCES thread(id) ON DELETE SET NULL,
        body        TEXT NOT NULL,
        occurred_on TEXT NOT NULL,
        created_at  TEXT NOT NULL
    );
    CREATE INDEX entry_person ON entry(person_id, occurred_on DESC);
    CREATE INDEX entry_thread ON entry(thread_id, occurred_on DESC);

    CREATE TABLE event (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id    INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
        thread_id    INTEGER REFERENCES thread(id) ON DELETE SET NULL,
        title        TEXT NOT NULL,
        on_date      TEXT NOT NULL,
        recurrence   TEXT NOT NULL DEFAULT 'none',
        lead_days    INTEGER NOT NULL DEFAULT 7,
        notes        TEXT NOT NULL DEFAULT '',
        done_at      TEXT,
        created_at   TEXT NOT NULL
    );
    CREATE INDEX event_date ON event(on_date);

    CREATE TABLE dismissal (
        key          TEXT PRIMARY KEY,
        snooze_until TEXT NOT NULL,
        created_at   TEXT NOT NULL
    );

    CREATE TABLE setting (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # Which circle someone belongs to. '' means not yet sorted, and the UI
    # groups those with 'other' so nobody silently disappears from the list.
    """
    ALTER TABLE person ADD COLUMN circle TEXT NOT NULL DEFAULT '';
    """,
]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def cursor():
    """A connection per request. Fine at this scale, and keeps threading simple."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def migrate() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for i, script in enumerate(MIGRATIONS[version:], start=version):
            conn.executescript(f"BEGIN; {script}; PRAGMA user_version = {i + 1}; COMMIT;")
    finally:
        conn.close()


# --- settings -------------------------------------------------------------
# Tunable without a redeploy. These drive the weekly review's thresholds.

DEFAULT_SETTINGS = {
    "birthday_lead_days": "14",
    "thread_quiet_days": "21",
    "person_quiet_days": "90",
    "review_horizon_days": "21",
}


def get_settings(conn: sqlite3.Connection) -> dict[str, str]:
    stored = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM setting")}
    return {**DEFAULT_SETTINGS, **stored}


def get_int_setting(conn: sqlite3.Connection, key: str) -> int:
    return int(get_settings(conn)[key])


def put_settings(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    for key, value in values.items():
        if key not in DEFAULT_SETTINGS:
            continue
        conn.execute(
            "INSERT INTO setting (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
