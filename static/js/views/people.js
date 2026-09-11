import { api } from "../api.js";
import { html, raw, initials, fmtDate, toast } from "../ui.js";
import { openPerson } from "../forms.js";

// '' (never sorted) is counted and filtered as "other", so nobody vanishes
// from the list just because you haven't categorised them yet.
const GROUPS = [
  { key: "family", label: "Family", plural: "family" },
  { key: "friend", label: "Friends", plural: "friends" },
  { key: "other", label: "Other", plural: "other" },
];

const circleOf = (person) => (person.circle === "family" || person.circle === "friend")
  ? person.circle
  : "other";

const STORAGE_KEY = "familia.people.filters";

function loadFilters() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (Array.isArray(saved) && saved.length) return new Set(saved);
  } catch { /* private window, cleared storage — fall through to the default */ }
  return new Set(GROUPS.map((g) => g.key));
}

function saveFilters(active) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...active]));
  } catch { /* not worth surfacing */ }
}

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
  const active = loadFilters();

  const counts = Object.fromEntries(GROUPS.map((g) => [g.key, 0]));
  for (const person of people) counts[circleOf(person)] += 1;

  const total = people.length;
  const breakdown = GROUPS
    .filter((g) => counts[g.key] > 0)
    .map((g) => `${counts[g.key]} ${g.plural}`)
    .join(" · ");

  mount.innerHTML = html`
    <div class="review-head row" style="justify-content:space-between">
      <div>
        <h1>People</h1>
        <p class="muted" id="tally"></p>
      </div>
      <button id="add-person">Add someone</button>
    </div>

    ${total > 0 ? raw(html`
      <div class="choices filters">
        ${raw(GROUPS.map((g) => html`
          <label class="choice">
            <input type="checkbox" data-circle="${g.key}" ${active.has(g.key) ? raw("checked") : ""}>
            <span>${g.label} <span class="muted">${counts[g.key]}</span></span>
          </label>`).join(""))}
      </div>`) : ""}

    <div id="rows"></div>`;

  const rows = mount.querySelector("#rows");
  const tally = mount.querySelector("#tally");

  const paint = () => {
    const shown = people.filter((p) => active.has(circleOf(p)));

    tally.textContent = total === 0
      ? "No one here yet."
      : shown.length === total
        ? `${total} ${total === 1 ? "person" : "people"}${breakdown ? ` · ${breakdown}` : ""}`
        : `Showing ${shown.length} of ${total}`;

    if (total === 0) {
      rows.innerHTML = html`
        <div class="card empty">
          <p>No one here yet.</p>
          <p class="muted" style="margin-top:6px">Start with the handful of people you think about most.</p>
        </div>`;
    } else if (shown.length === 0) {
      rows.innerHTML = html`
        <div class="card empty">
          <p class="muted">Every circle is filtered out.</p>
        </div>`;
    } else {
      rows.innerHTML = shown.map(rowMarkup).join("");
    }
  };

  paint();

  mount.querySelectorAll("input[data-circle]").forEach((box) => {
    box.onchange = () => {
      if (box.checked) active.add(box.dataset.circle);
      else active.delete(box.dataset.circle);
      saveFilters(active);
      paint();
    };
  });

  mount.querySelector("#add-person").onclick = () =>
    openPerson({
      onDone: (saved) => {
        toast(`Added ${saved.name}`);
        location.hash = `#/person/${saved.id}`;
      },
    });
}
