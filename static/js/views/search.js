import { api } from "../api.js";
import { html, raw, initials, fmtDate } from "../ui.js";

export async function render(mount, query) {
  mount.innerHTML = `<p class="muted">Searching…</p>`;
  const { people, entries } = await api.search(query);

  if (people.length === 0 && entries.length === 0) {
    mount.innerHTML = html`
      <div class="review-head"><h1>No matches</h1>
      <p class="muted">Nothing for “${query}”.</p></div>`;
    return;
  }

  mount.innerHTML = html`
    <div class="review-head">
      <h1>Results</h1>
      <p class="muted">For “${query}”.</p>
    </div>

    ${people.length ? raw(html`
      <div class="section-head"><h2>People</h2></div>
      ${raw(people.map((p) => html`
        <a class="person-row" href="#/person/${p.id}">
          <div class="avatar">${initials(p.name)}</div>
          <div class="meta">
            <div class="name">${p.name}</div>
            <div class="sub">${[p.relationship, p.location].filter(Boolean).join(" · ")}</div>
          </div>
        </a>`).join(""))}`) : ""}

    ${entries.length ? raw(html`
      <div class="section-head"><h2>Notes</h2></div>
      <div class="card">
        ${raw(entries.map((e) => html`
          <div class="entry">
            <div class="head">
              <a href="#/person/${e.person_id}">${e.person_name}</a>
              <span>${fmtDate(e.occurred_on, { withYear: true })}</span>
            </div>
            <div class="body">${e.body}</div>
          </div>`).join(""))}
      </div>`) : ""}`;
}
