# familia

A personal relationship manager. One user, self-hosted, built to be reviewed once a week.

Trello can hold this data but can't compute *what matters this week*. That
computation is the whole product; everything else is storage.

## The model

| Entity | What it holds |
|---|---|
| **Person** | The portrait. Basics (birthday, where they live, family) and character notes — quirks, what they care about, how to be good to them. |
| **Thread** | An open situation in their life you want to stay on top of. Written once, closed when it resolves. |
| **Log entry** | A timestamped note, optionally filed against a thread. The only thing you write often. |
| **Event** | A date. One-off (an appointment) or yearly (an anniversary). Birthdays come from the person record, not from events. |

No habit trackers, no per-person contact frequency to configure. Both add
friction faster than they add value.

## The weekly review

`/` generates a short list from three signals:

- **dated** — an event or birthday has entered its lead time. Birthdays default
  to 14 days ahead, because a reminder on the day is how you miss it.
- **quiet** — an open thread with nothing written against it lately (default 21 days).
- **drift** — a person with no notes in a long while (default 90 days), only for
  people with no open thread already surfacing.

The last two are the cadence replacement: you never configure a frequency, it's
inferred from your own writing. Thresholds live in Settings.

Snoozing an item hides it for a week. Snooze keys carry the occurrence date, so
snoozing this year's birthday never suppresses next year's.

## Running it locally

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

FAMILIA_PASSWORD=whatever \
FAMILIA_SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))') \
FAMILIA_INSECURE_COOKIES=1 \
.venv/bin/uvicorn app.main:app --reload --port 8771
```

Then open http://localhost:8771. `FAMILIA_INSECURE_COOKIES=1` is only for
plain-HTTP localhost; never set it in production.

## Tests

```sh
.venv/bin/python tests/test_review.py
```

Covers the review engine: lead times, leap-year birthdays, year rollover,
snooze expiry, thread and drift thresholds, archiving, ordering.

## Environment

| Variable | Purpose |
|---|---|
| `FAMILIA_PASSWORD` | **Required.** The single password. Without it, login always fails. |
| `FAMILIA_SECRET_KEY` | **Set this in production.** Signs the session cookie. Unset means a random key per boot, so every restart signs you out. |
| `FAMILIA_DB` | SQLite path. Defaults to `data/familia.db`. |
| `FAMILIA_INSECURE_COOKIES` | Set to `1` only for HTTP localhost. |

## Deploying to fly.io

```sh
fly launch --no-deploy                      # keeps the bundled fly.toml
fly volumes create familia_data --size 1    # SQLite lives here
fly secrets set FAMILIA_PASSWORD='...' \
                FAMILIA_SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
fly deploy
```

**Keep it to one machine.** `fly scale count 1`. SQLite sits on a volume, and a
second machine would get its own volume and silently diverge from the first.

`auto_stop_machines` is on, so it suspends when idle and wakes on request —
a personal app costs close to nothing to run this way.

### Backups

The database is one file. Volume snapshots are automatic, but pull your own copy
too:

```sh
fly ssh console -C "sqlite3 /data/familia.db .dump" > familia-$(date +%F).sql
```

This holds health details about your family. Keep it on your own Fly app, keep
the password strong, and don't put it behind a third-party service.

## Shortcuts

`n` writes a note from anywhere, `/` jumps to search.
