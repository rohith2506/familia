# familia

A personal relationship manager. One user, self-hosted, built to be reviewed once a week.

Trello can hold this data but can't compute *what matters this week*. That
computation is the whole product; everything else is storage.

## The model

| Entity | What it holds |
|---|---|
| **Person** | The portrait. A circle (family / friend / other), basics (birthday, where they live, family) and character notes — quirks, what they care about, how to be good to them. |
| **Thread** | An open situation in their life you want to stay on top of. Written once, closed when it resolves. |
| **Log entry** | A timestamped note, optionally filed against a thread. The only thing you write often. |
| **Event** | A date. One-off, or repeating daily / weekly / fortnightly / monthly / quarterly / yearly. Birthdays come from the person record, not from events. |

Repeating dates step from their original anchor, so a monthly date set on the
31st shows as the 30th in September and the 28th in February, then returns to
the 31st — it never walks backwards through the month. A lead time is capped
just under its own interval (a daily date leads by 0, a weekly one by at most
6), otherwise a short repeat would sit in the review permanently.

`app/review.py` and `static/js/ui.js` each implement this date maths — the
server to build the review, the browser to show the next date on a portrait.
They are checked against each other over every anchor × repeat × date
combination; see the differential test note in Tests below.

No habit trackers, no per-person contact frequency to configure. Both add
friction faster than they add value.

The People list shows a running count — `12 people · 5 family · 6 friends · 1 other`
— and checkboxes to filter by circle. Anyone you haven't sorted yet counts as
"other", so nobody disappears from the list. The filter choice is remembered in
the browser.

## The weekly review

`/` generates a short list from three signals:

- **dated** — an event or birthday has entered its lead time. Birthdays default
  to 14 days ahead, because a reminder on the day is how you miss it.
- **quiet** — an open thread with nothing written against it lately (default 21 days).
- **drift** — a person with no notes in a long while (default 90 days), only for
  people with no open thread already surfacing.

The last two are the cadence replacement: you never configure a frequency, it's
inferred from your own writing. Thresholds live in Settings.

"Mark done" retires a one-off for good. A repeat is never finished, so its
button reads "Done this time" and clears only that occurrence.

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

Covers the review engine: lead times and their per-interval caps, every repeat
interval, month-end clamping without drift, leap-year birthdays, year rollover,
snooze expiry, thread and drift thresholds, archiving, ordering.

The Python and JavaScript implementations of the recurrence maths are kept in
step by a differential check over ~2,700 anchor × repeat × date combinations.
If you change one, change the other and re-run it.

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
