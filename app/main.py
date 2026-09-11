"""familia — a personal relationship manager.

One user, one SQLite file, one process. The API is plain JSON; the frontend
in static/ is vanilla ES modules with no build step.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import auth, db
from .review import build_review, dismiss

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="familia", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup() -> None:
    db.migrate()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


Guard = Annotated[None, Depends(auth.require_auth)]


# --- schemas --------------------------------------------------------------


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    relationship: str = ""
    birth_year: int | None = None
    birth_month: int | None = Field(default=None, ge=1, le=12)
    birth_day: int | None = Field(default=None, ge=1, le=31)
    location: str = ""
    basics: str = ""
    character_notes: str = ""
    archived: bool = False

    @field_validator("birth_year")
    @classmethod
    def _sane_year(cls, v: int | None) -> int | None:
        if v is not None and not (1900 <= v <= date.today().year):
            raise ValueError("birth_year out of range")
        return v


class PersonPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    relationship: str | None = None
    birth_year: int | None = None
    birth_month: int | None = Field(default=None, ge=1, le=12)
    birth_day: int | None = Field(default=None, ge=1, le=31)
    location: str | None = None
    basics: str | None = None
    character_notes: str | None = None
    archived: bool | None = None


class ThreadIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    detail: str = ""


class ThreadPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    detail: str | None = None
    status: Literal["open", "closed"] | None = None


class EntryIn(BaseModel):
    body: str = Field(min_length=1)
    occurred_on: date | None = None
    thread_id: int | None = None


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    on_date: date
    recurrence: Literal["none", "yearly"] = "none"
    lead_days: int = Field(default=7, ge=0, le=365)
    notes: str = ""
    thread_id: int | None = None


class EventPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    on_date: date | None = None
    recurrence: Literal["none", "yearly"] | None = None
    lead_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = None
    thread_id: int | None = None
    done: bool | None = None


class DismissIn(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    days: int = Field(default=7, ge=1, le=365)


# --- helpers --------------------------------------------------------------


def _patch_sql(table: str, row_id: int, fields: dict[str, Any], touch: bool = True) -> tuple[str, list]:
    if touch:
        fields["updated_at"] = now()
    assigns = ", ".join(f"{k} = ?" for k in fields)
    return f"UPDATE {table} SET {assigns} WHERE id = ?", [*fields.values(), row_id]


def _person_or_404(conn, person_id: int) -> dict:
    row = conn.execute("SELECT * FROM person WHERE id = ?", (person_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No such person")
    return dict(row)


# --- auth -----------------------------------------------------------------


@app.get("/login")
def login_page(request: Request):
    if auth.is_authenticated(request):
        return RedirectResponse("/", status_code=303)
    return FileResponse(STATIC_DIR / "login.html")


@app.post("/login")
def login(response: Response, password: Annotated[str, Form()]):
    if not auth.password_is_set():
        raise HTTPException(500, "FAMILIA_PASSWORD is not configured on the server")
    if not auth.check_password(password):
        return RedirectResponse("/login?error=1", status_code=303)
    redirect = RedirectResponse("/", status_code=303)
    auth.issue_session(redirect)
    return redirect


@app.post("/logout")
def logout():
    redirect = RedirectResponse("/login", status_code=303)
    auth.clear_session(redirect)
    return redirect


# --- review ---------------------------------------------------------------


@app.get("/api/review")
def get_review(_: Guard):
    with db.cursor() as conn:
        return build_review(conn)


@app.post("/api/review/dismiss")
def post_dismiss(_: Guard, payload: DismissIn):
    with db.cursor() as conn:
        dismiss(conn, payload.key, payload.days)
    return {"ok": True}


# --- people ---------------------------------------------------------------


@app.get("/api/people")
def list_people(_: Guard, include_archived: bool = False):
    clause = "" if include_archived else "WHERE archived = 0"
    with db.cursor() as conn:
        rows = conn.execute(
            f"""
            SELECT p.*,
                   (SELECT COUNT(*) FROM thread t
                     WHERE t.person_id = p.id AND t.status = 'open') AS open_threads,
                   (SELECT MAX(occurred_on) FROM entry e WHERE e.person_id = p.id) AS last_entry_on
              FROM person p {clause}
             ORDER BY p.name COLLATE NOCASE
            """
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/people", status_code=201)
def create_person(_: Guard, payload: PersonIn):
    stamp = now()
    with db.cursor() as conn:
        cur = conn.execute(
            """
            INSERT INTO person (name, relationship, birth_year, birth_month, birth_day,
                                location, basics, character_notes, archived, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name.strip(), payload.relationship, payload.birth_year,
                payload.birth_month, payload.birth_day, payload.location,
                payload.basics, payload.character_notes, int(payload.archived), stamp, stamp,
            ),
        )
        return _person_or_404(conn, cur.lastrowid)


@app.get("/api/people/{person_id}")
def get_person(_: Guard, person_id: int):
    """The portrait: everything about one person on a single screen."""
    with db.cursor() as conn:
        person = _person_or_404(conn, person_id)
        person["threads"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM thread WHERE person_id = ? "
                "ORDER BY status = 'closed', updated_at DESC",
                (person_id,),
            )
        ]
        person["entries"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM entry WHERE person_id = ? "
                "ORDER BY occurred_on DESC, id DESC LIMIT 200",
                (person_id,),
            )
        ]
        person["events"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM event WHERE person_id = ? ORDER BY on_date",
                (person_id,),
            )
        ]
        return person


@app.patch("/api/people/{person_id}")
def patch_person(_: Guard, person_id: int, payload: PersonPatch):
    fields = payload.model_dump(exclude_unset=True)
    if "archived" in fields:
        fields["archived"] = int(fields["archived"])
    with db.cursor() as conn:
        _person_or_404(conn, person_id)
        if fields:
            conn.execute(*_patch_sql("person", person_id, fields))
        return _person_or_404(conn, person_id)


@app.delete("/api/people/{person_id}", status_code=204)
def delete_person(_: Guard, person_id: int):
    with db.cursor() as conn:
        _person_or_404(conn, person_id)
        conn.execute("DELETE FROM person WHERE id = ?", (person_id,))
    return Response(status_code=204)


# --- threads --------------------------------------------------------------


@app.post("/api/people/{person_id}/threads", status_code=201)
def create_thread(_: Guard, person_id: int, payload: ThreadIn):
    stamp = now()
    with db.cursor() as conn:
        _person_or_404(conn, person_id)
        cur = conn.execute(
            "INSERT INTO thread (person_id, title, detail, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'open', ?, ?)",
            (person_id, payload.title.strip(), payload.detail, stamp, stamp),
        )
        row = conn.execute("SELECT * FROM thread WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


@app.patch("/api/threads/{thread_id}")
def patch_thread(_: Guard, thread_id: int, payload: ThreadPatch):
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("status") == "closed":
        fields["closed_at"] = now()
    elif fields.get("status") == "open":
        fields["closed_at"] = None
    with db.cursor() as conn:
        if conn.execute("SELECT 1 FROM thread WHERE id = ?", (thread_id,)).fetchone() is None:
            raise HTTPException(404, "No such thread")
        if fields:
            conn.execute(*_patch_sql("thread", thread_id, fields))
        return dict(conn.execute("SELECT * FROM thread WHERE id = ?", (thread_id,)).fetchone())


@app.delete("/api/threads/{thread_id}", status_code=204)
def delete_thread(_: Guard, thread_id: int):
    with db.cursor() as conn:
        conn.execute("DELETE FROM thread WHERE id = ?", (thread_id,))
    return Response(status_code=204)


# --- entries --------------------------------------------------------------


@app.post("/api/people/{person_id}/entries", status_code=201)
def create_entry(_: Guard, person_id: int, payload: EntryIn):
    occurred = (payload.occurred_on or date.today()).isoformat()
    with db.cursor() as conn:
        _person_or_404(conn, person_id)
        if payload.thread_id is not None:
            owner = conn.execute(
                "SELECT person_id FROM thread WHERE id = ?", (payload.thread_id,)
            ).fetchone()
            if owner is None or owner["person_id"] != person_id:
                raise HTTPException(400, "Thread does not belong to this person")
        cur = conn.execute(
            "INSERT INTO entry (person_id, thread_id, body, occurred_on, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (person_id, payload.thread_id, payload.body.strip(), occurred, now()),
        )
        # Writing against a thread counts as touching it.
        if payload.thread_id is not None:
            conn.execute(
                "UPDATE thread SET updated_at = ? WHERE id = ?", (now(), payload.thread_id)
            )
        return dict(conn.execute("SELECT * FROM entry WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.delete("/api/entries/{entry_id}", status_code=204)
def delete_entry(_: Guard, entry_id: int):
    with db.cursor() as conn:
        conn.execute("DELETE FROM entry WHERE id = ?", (entry_id,))
    return Response(status_code=204)


# --- events ---------------------------------------------------------------


@app.post("/api/people/{person_id}/events", status_code=201)
def create_event(_: Guard, person_id: int, payload: EventIn):
    with db.cursor() as conn:
        _person_or_404(conn, person_id)
        cur = conn.execute(
            """
            INSERT INTO event (person_id, thread_id, title, on_date, recurrence,
                               lead_days, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person_id, payload.thread_id, payload.title.strip(),
                payload.on_date.isoformat(), payload.recurrence,
                payload.lead_days, payload.notes, now(),
            ),
        )
        return dict(conn.execute("SELECT * FROM event WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.patch("/api/events/{event_id}")
def patch_event(_: Guard, event_id: int, payload: EventPatch):
    fields = payload.model_dump(exclude_unset=True)
    if "done" in fields:
        fields["done_at"] = now() if fields.pop("done") else None
    if isinstance(fields.get("on_date"), date):
        fields["on_date"] = fields["on_date"].isoformat()
    with db.cursor() as conn:
        if conn.execute("SELECT 1 FROM event WHERE id = ?", (event_id,)).fetchone() is None:
            raise HTTPException(404, "No such event")
        if fields:
            conn.execute(*_patch_sql("event", event_id, fields, touch=False))
        return dict(conn.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone())


@app.delete("/api/events/{event_id}", status_code=204)
def delete_event(_: Guard, event_id: int):
    with db.cursor() as conn:
        conn.execute("DELETE FROM event WHERE id = ?", (event_id,))
    return Response(status_code=204)


# --- search & settings ----------------------------------------------------


@app.get("/api/search")
def search(_: Guard, q: str = ""):
    q = q.strip()
    if len(q) < 2:
        return {"people": [], "entries": []}
    like = f"%{q}%"
    with db.cursor() as conn:
        people = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM person WHERE name LIKE ? OR relationship LIKE ? "
                "OR basics LIKE ? OR character_notes LIKE ? ORDER BY name COLLATE NOCASE LIMIT 25",
                (like, like, like, like),
            )
        ]
        entries = [
            dict(r)
            for r in conn.execute(
                "SELECT e.*, p.name AS person_name FROM entry e JOIN person p ON p.id = e.person_id "
                "WHERE e.body LIKE ? ORDER BY e.occurred_on DESC LIMIT 50",
                (like,),
            )
        ]
        return {"people": people, "entries": entries}


@app.get("/api/settings")
def read_settings(_: Guard):
    with db.cursor() as conn:
        return db.get_settings(conn)


@app.patch("/api/settings")
def write_settings(_: Guard, payload: dict[str, str]):
    with db.cursor() as conn:
        db.put_settings(conn, payload)
        return db.get_settings(conn)


# --- frontend -------------------------------------------------------------


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def index(request: Request):
    if not auth.is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return FileResponse(STATIC_DIR / "index.html")


@app.exception_handler(401)
def unauthorized(request: Request, exc: HTTPException):
    return JSONResponse({"detail": "Not signed in"}, status_code=401)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
