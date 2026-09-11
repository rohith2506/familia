import { api } from "../api.js";
import { html, raw, initials, fmtDate, toast } from "../ui.js";
import { openPerson } from "../forms.js";

function subtitle(person) {
  const bits = [];
  if (person.relationship) bits.push(person.relationship);
  if (person.location) bits.push(person.location);
  if (person.last_entry_on) bits.push(`last note ${fmtDate(person.last_entry_on)}`);
  else bits.push("no notes yet");
  return bits.join(" · ");
}

function rowMarkup(person) {
  return html`
    <a class="person-row" href="#/person/${person.id}">
      <div class="avatar">${initials(person.name)}</div>
      <div class="meta">
        <div class="name">${person.name}</div>
        <div class="sub">${subtitle(person)}</div>
      </div>
      ${person.open_threads > 0
        ? raw(html`<span class="pill open">${person.open_threads} open</span>`)
        : ""}
    </a>`;
}

export async function render(mount) {
  mount.innerHTML = `<p class="muted">Loading…</p>`;
  const people = await api.people();

  mount.innerHTML = html`
    <div class="review-head row" style="justify-content:space-between">
      <h1>People</h1>
      <button id="add-person">Add someone</button>
    </div>
    ${people.length === 0
      ? raw(html`<div class="card empty">
            <p>No one here yet.</p>
            <p class="muted" style="margin-top:6px">Start with the handful of people you think about most.</p>
          </div>`)
      : raw(people.map(rowMarkup).join(""))}`;

  mount.querySelector("#add-person").onclick = () =>
    openPerson({
      onDone: (saved) => {
        toast(`Added ${saved.name}`);
        location.hash = `#/person/${saved.id}`;
      },
    });
}
