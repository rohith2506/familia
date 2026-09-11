// The portrait: everything about one person on a single screen.

import { api } from "../api.js";
import { html, raw, initials, fmtDate, fmtDayLabel, parseISO, todayISO, toast, confirmDelete } from "../ui.js";
import { openNote, openPerson, openThread, openEvent } from "../forms.js";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"];

function birthdayLine(person) {
  if (!person.birth_month || !person.birth_day) return null;
  const label = `${MONTHS[person.birth_month - 1]} ${person.birth_day}`;
  if (!person.birth_year) return `Birthday ${label}`;

  const today = new Date();
  let next = new Date(today.getFullYear(), person.birth_month - 1, person.birth_day);
  if (next < parseISO(todayISO())) next = new Date(today.getFullYear() + 1, person.birth_month - 1, person.birth_day);
  return `Birthday ${label} · turning ${next.getFullYear() - person.birth_year}`;
}

function nextOccurrence(event) {
  const on = parseISO(event.on_date);
  if (event.recurrence !== "yearly") return event.on_date;
  const today = parseISO(todayISO());
  const year = new Date(today.getFullYear(), on.getMonth(), on.getDate()) >= today
    ? today.getFullYear()
    : today.getFullYear() + 1;
  return `${year}-${String(on.getMonth() + 1).padStart(2, "0")}-${String(on.getDate()).padStart(2, "0")}`;
}

function threadMarkup(thread) {
  const closed = thread.status === "closed";
  return html`
    <div class="thread ${closed ? "closed" : ""}" data-thread="${thread.id}">
      <div class="title">${thread.title}</div>
      ${thread.detail ? raw(html`<div class="prose" style="font-size:.9rem">${thread.detail}</div>`) : ""}
      <div class="item-actions">
        <button class="link" data-act="thread-note" data-id="${thread.id}">Note</button>
        <button class="link" data-act="thread-edit" data-id="${thread.id}">Edit</button>
        <button class="link" data-act="thread-toggle" data-id="${thread.id}"
                data-status="${thread.status}">${closed ? "Reopen" : "Close"}</button>
        <button class="link" data-act="thread-delete" data-id="${thread.id}">Delete</button>
      </div>
    </div>`;
}

function eventMarkup(event) {
  const when = nextOccurrence(event);
  const past = event.recurrence === "none" && (event.done_at || parseISO(when) < parseISO(todayISO()));
  return html`
    <div class="date-row" data-event="${event.id}" style="${past ? "opacity:.55" : ""}">
      <div class="d">${fmtDate(when)}<br><span style="font-size:.75rem">${past ? "past" : fmtDayLabel(when)}</span></div>
      <div style="flex:1 1 auto;min-width:0">
        <div>${event.title}${event.recurrence === "yearly" ? raw(' <span class="pill">yearly</span>') : ""}</div>
        ${event.notes ? raw(html`<div class="muted" style="font-size:.85rem">${event.notes}</div>`) : ""}
      </div>
      <button class="link" data-act="event-edit" data-id="${event.id}">Edit</button>
      <button class="link" data-act="event-delete" data-id="${event.id}">Delete</button>
    </div>`;
}

function entryMarkup(entry, threadsById) {
  const thread = entry.thread_id ? threadsById.get(entry.thread_id) : null;
  return html`
    <div class="entry" data-entry="${entry.id}">
      <div class="head">
        <span>${fmtDate(entry.occurred_on, { withYear: true })}</span>
        ${thread ? raw(html`<span class="pill">${thread.title}</span>`) : ""}
        <button class="link" style="margin-left:auto;font-size:.75rem"
                data-act="entry-delete" data-id="${entry.id}">Delete</button>
      </div>
      <div class="body">${entry.body}</div>
    </div>`;
}

export async function render(mount, personId) {
  mount.innerHTML = `<p class="muted">Loading…</p>`;
  const person = await api.person(personId);
  const reload = () => render(mount, personId);

  const threadsById = new Map(person.threads.map((t) => [t.id, t]));
  const openThreads = person.threads.filter((t) => t.status === "open");
  const closedThreads = person.threads.filter((t) => t.status === "closed");
  const birthday = birthdayLine(person);
  const facts = [person.relationship, person.location, birthday].filter(Boolean).join(" · ");

  const upcoming = person.events
    .map((e) => ({ ...e, _when: nextOccurrence(e) }))
    .sort((a, b) => a._when.localeCompare(b._when));

  mount.innerHTML = html`
    <div class="portrait-head">
      <div class="avatar">${initials(person.name)}</div>
      <div style="flex:1 1 auto;min-width:0">
        <h1>${person.name}</h1>
        <p class="muted" style="font-size:.9rem">${facts || "No details yet"}</p>
      </div>
      <button class="ghost" id="edit-person">Edit</button>
    </div>

    ${(person.basics || person.character_notes) ? raw(html`
      <div class="card">
        ${person.basics ? raw(html`
          <h3 style="color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.07em">Basics</h3>
          <div class="prose" style="margin-bottom:${person.character_notes ? "14px" : "0"}">${person.basics}</div>`) : ""}
        ${person.character_notes ? raw(html`
          <h3 style="color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.07em">What to know</h3>
          <div class="prose">${person.character_notes}</div>`) : ""}
      </div>`) : ""}

    <div class="section-head">
      <h2>Open threads</h2>
      <button class="link" id="add-thread">+ New thread</button>
    </div>
    <div class="card">
      ${openThreads.length
        ? raw(openThreads.map(threadMarkup).join(""))
        : raw('<p class="muted" style="font-size:.9rem">Nothing open. Start a thread when something in their life needs following.</p>')}
      ${closedThreads.length ? raw(html`
        <details style="margin-top:12px">
          <summary class="muted" style="cursor:pointer;font-size:.85rem">${closedThreads.length} closed</summary>
          <div style="margin-top:12px">${raw(closedThreads.map(threadMarkup).join(""))}</div>
        </details>`) : ""}
    </div>

    <div class="section-head">
      <h2>Dates</h2>
      <button class="link" id="add-event">+ Add a date</button>
    </div>
    <div class="card">
      ${upcoming.length
        ? raw(upcoming.map(eventMarkup).join(""))
        : raw('<p class="muted" style="font-size:.9rem">No dates yet. Birthdays come from the profile above.</p>')}
    </div>

    <div class="section-head">
      <h2>Timeline</h2>
      <button class="link" id="add-note">+ Note with details</button>
    </div>
    <div class="card">
      <form id="quick-note" style="margin-bottom:${person.entries.length ? "8px" : "0"}">
        <textarea name="body" placeholder="What happened? (saves against today)"
                  style="min-height:64px"></textarea>
        <div class="row" style="justify-content:flex-end;margin-top:8px">
          <button type="submit" class="tiny">Save note</button>
        </div>
      </form>
      <div class="timeline">
        ${person.entries.length
          ? raw(person.entries.map((e) => entryMarkup(e, threadsById)).join(""))
          : ""}
      </div>
    </div>

    <div class="row" style="justify-content:flex-end;margin-top:20px">
      <button class="link" id="delete-person" style="color:var(--muted)">Delete ${person.name}</button>
    </div>`;

  // --- wiring ------------------------------------------------------------

  mount.querySelector("#quick-note").onsubmit = async (e) => {
    e.preventDefault();
    const field = e.target.querySelector("textarea");
    const body = field.value.trim();
    if (!body) return;
    try {
      await api.createEntry(person.id, { body, occurred_on: todayISO() });
      toast("Noted");
      reload();
    } catch (err) {
      toast(err.message);
    }
  };

  mount.querySelector("#edit-person").onclick = () => openPerson({ person, onDone: reload });
  mount.querySelector("#add-thread").onclick = () => openThread({ personId: person.id, onDone: reload });
  mount.querySelector("#add-event").onclick = () =>
    openEvent({ personId: person.id, threads: person.threads, onDone: reload });
  mount.querySelector("#add-note").onclick = () =>
    openNote({ personId: person.id, personName: person.name, threads: person.threads, onDone: reload });

  mount.querySelector("#delete-person").onclick = async () => {
    if (!confirmDelete(`${person.name} and everything recorded about them`)) return;
    await api.deletePerson(person.id);
    location.hash = "#/people";
  };

  mount.onclick = async (e) => {
    const button = e.target.closest("button[data-act]");
    if (!button) return;
    const id = Number(button.dataset.id);
    try {
      switch (button.dataset.act) {
        case "thread-note":
          openNote({
            personId: person.id, personName: person.name,
            threads: person.threads, threadId: id, onDone: reload,
          });
          break;
        case "thread-edit":
          openThread({ personId: person.id, thread: threadsById.get(id), onDone: reload });
          break;
        case "thread-toggle":
          await api.updateThread(id, {
            status: button.dataset.status === "open" ? "closed" : "open",
          });
          reload();
          break;
        case "thread-delete":
          if (!confirmDelete("this thread")) return;
          await api.deleteThread(id);
          reload();
          break;
        case "event-edit":
          openEvent({
            personId: person.id, threads: person.threads,
            event: person.events.find((ev) => ev.id === id), onDone: reload,
          });
          break;
        case "event-delete":
          if (!confirmDelete("this date")) return;
          await api.deleteEvent(id);
          reload();
          break;
        case "entry-delete":
          if (!confirmDelete("this note")) return;
          await api.deleteEntry(id);
          reload();
          break;
      }
    } catch (err) {
      toast(err.message);
    }
  };
}
