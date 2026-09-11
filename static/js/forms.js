// Shared modal forms. Each resolves by calling onDone() so the caller can
// re-render whatever view it owns.

import { api } from "./api.js";
import { html, raw, modal, toast, todayISO, confirmDelete } from "./ui.js";

const MONTH_OPTIONS = ["January", "February", "March", "April", "May", "June", "July",
                       "August", "September", "October", "November", "December"];

function threadOptions(threads, selected) {
  return threads
    .filter((t) => t.status === "open")
    .map((t) => html`<option value="${t.id}" ${selected === t.id ? raw("selected") : ""}>${t.title}</option>`)
    .join("");
}

/** The fast path: pick a person, type, save. Everything else is optional. */
export function openNote({ personId = null, personName = "", threads = [], threadId = null, onDone }) {
  const fixed = personId !== null;

  const build = (people) => {
    const personField = fixed
      ? ""
      : html`<label for="person">Who</label>
             <select id="person" name="person_id" required>
               <option value="">Choose someone…</option>
               ${raw(people.map((p) => html`<option value="${p.id}">${p.name}</option>`).join(""))}
             </select>`;

    modal({
      title: fixed ? `Note about ${personName}` : "Write a note",
      body: html`
        ${raw(personField)}
        <label for="body">What happened</label>
        <textarea id="body" name="body" required placeholder="Anything you'd want to remember."></textarea>
        <div class="grid-2">
          <div>
            <label for="occurred">When</label>
            <input id="occurred" name="occurred_on" type="date" value="${todayISO()}">
          </div>
          <div>
            <label for="thread">Part of a thread</label>
            <select id="thread" name="thread_id">
              <option value="">No thread</option>
              ${raw(threadOptions(threads, threadId))}
            </select>
          </div>
        </div>`,
      submitLabel: "Save note",
      onSubmit: async (form) => {
        const data = new FormData(form);
        const who = fixed ? personId : Number(data.get("person_id"));
        if (!who) { toast("Pick someone first"); return false; }
        await api.createEntry(who, {
          body: data.get("body"),
          occurred_on: data.get("occurred_on") || todayISO(),
          thread_id: data.get("thread_id") ? Number(data.get("thread_id")) : null,
        });
        toast("Noted");
        onDone?.();
        return true;
      },
    });

    // Capturing from the fab: load the chosen person's threads on the fly so a
    // note can still be filed against one without a second trip.
    if (!fixed) {
      const select = document.querySelector("#person");
      select?.addEventListener("change", async () => {
        const threadSelect = document.querySelector("#thread");
        threadSelect.innerHTML = `<option value="">No thread</option>`;
        if (!select.value) return;
        const person = await api.person(Number(select.value));
        threadSelect.insertAdjacentHTML("beforeend", threadOptions(person.threads, null));
      });
    }
  };

  if (fixed) build([]);
  else api.people().then(build).catch((e) => toast(e.message));
}

export function openPerson({ person = null, onDone }) {
  const editing = person !== null;
  const v = person ?? {};

  modal({
    title: editing ? `Edit ${v.name}` : "Add someone",
    body: html`
      <label for="name">Name</label>
      <input id="name" name="name" type="text" required value="${v.name ?? ""}">

      <div class="grid-2">
        <div>
          <label for="relationship">Relationship</label>
          <input id="relationship" name="relationship" type="text"
                 placeholder="mother, close friend…" value="${v.relationship ?? ""}">
        </div>
        <div>
          <label for="location">Where they are</label>
          <input id="location" name="location" type="text" value="${v.location ?? ""}">
        </div>
      </div>

      <label>Birthday</label>
      <div class="row">
        <select name="birth_month" style="flex:1 1 120px">
          <option value="">Month</option>
          ${raw(MONTH_OPTIONS.map((m, i) =>
            html`<option value="${i + 1}" ${v.birth_month === i + 1 ? raw("selected") : ""}>${m}</option>`).join(""))}
        </select>
        <input name="birth_day" type="number" min="1" max="31" placeholder="Day"
               style="flex:0 1 90px" value="${v.birth_day ?? ""}">
        <input name="birth_year" type="number" min="1900" max="2100" placeholder="Year (optional)"
               style="flex:1 1 130px" value="${v.birth_year ?? ""}">
      </div>

      <label for="basics">Basics</label>
      <textarea id="basics" name="basics"
        placeholder="Partner, kids, work, anything factual you'd forget.">${v.basics ?? ""}</textarea>

      <label for="character">What to know about them</label>
      <textarea id="character" name="character_notes"
        placeholder="Quirks, what they care about, how to be good to them, what not to bring up.">${v.character_notes ?? ""}</textarea>`,
    submitLabel: editing ? "Save" : "Add",
    onSubmit: async (form) => {
      const data = new FormData(form);
      const num = (key) => (data.get(key) ? Number(data.get(key)) : null);
      const payload = {
        name: data.get("name").trim(),
        relationship: data.get("relationship"),
        location: data.get("location"),
        birth_month: num("birth_month"),
        birth_day: num("birth_day"),
        birth_year: num("birth_year"),
        basics: data.get("basics"),
        character_notes: data.get("character_notes"),
      };
      const saved = editing
        ? await api.updatePerson(v.id, payload)
        : await api.createPerson(payload);
      onDone?.(saved);
      return true;
    },
  });
}

export function openThread({ personId, thread = null, onDone }) {
  const editing = thread !== null;
  modal({
    title: editing ? "Edit thread" : "New thread",
    subtitle: "Something going on in their life you want to stay on top of.",
    body: html`
      <label for="title">What's going on</label>
      <input id="title" name="title" type="text" required
             placeholder="Managing her heart condition" value="${thread?.title ?? ""}">
      <label for="detail">Context</label>
      <textarea id="detail" name="detail"
        placeholder="The situation, what you should know, what you're watching for.">${thread?.detail ?? ""}</textarea>`,
    submitLabel: editing ? "Save" : "Open thread",
    onSubmit: async (form) => {
      const data = new FormData(form);
      const payload = { title: data.get("title").trim(), detail: data.get("detail") };
      if (editing) await api.updateThread(thread.id, payload);
      else await api.createThread(personId, payload);
      onDone?.();
      return true;
    },
  });
}

export function openEvent({ personId, threads = [], event = null, onDone }) {
  const editing = event !== null;
  modal({
    title: editing ? "Edit date" : "Add a date",
    body: html`
      <label for="title">What</label>
      <input id="title" name="title" type="text" required
             placeholder="Cardiology appointment" value="${event?.title ?? ""}">

      <div class="grid-2">
        <div>
          <label for="on_date">When</label>
          <input id="on_date" name="on_date" type="date" required value="${event?.on_date ?? todayISO()}">
        </div>
        <div>
          <label for="recurrence">Repeats</label>
          <select id="recurrence" name="recurrence">
            <option value="none" ${event?.recurrence === "yearly" ? "" : raw("selected")}>Once</option>
            <option value="yearly" ${event?.recurrence === "yearly" ? raw("selected") : ""}>Every year</option>
          </select>
        </div>
      </div>

      <div class="grid-2">
        <div>
          <label for="lead">Warn me this many days ahead</label>
          <input id="lead" name="lead_days" type="number" min="0" max="365" value="${event?.lead_days ?? 7}">
        </div>
        <div>
          <label for="thread">Related thread</label>
          <select id="thread" name="thread_id">
            <option value="">None</option>
            ${raw(threadOptions(threads, event?.thread_id ?? null))}
          </select>
        </div>
      </div>

      <label for="notes">Notes</label>
      <textarea id="notes" name="notes"
        placeholder="What to ask, what to bring.">${event?.notes ?? ""}</textarea>`,
    submitLabel: editing ? "Save" : "Add",
    onSubmit: async (form) => {
      const data = new FormData(form);
      const payload = {
        title: data.get("title").trim(),
        on_date: data.get("on_date"),
        recurrence: data.get("recurrence"),
        lead_days: Number(data.get("lead_days") || 7),
        notes: data.get("notes"),
        thread_id: data.get("thread_id") ? Number(data.get("thread_id")) : null,
      };
      if (editing) await api.updateEvent(event.id, payload);
      else await api.createEvent(personId, payload);
      onDone?.();
      return true;
    },
  });
}

export { confirmDelete };
