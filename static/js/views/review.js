// The weekly review — the home screen, and the reason the app exists.

import { api } from "../api.js";
import { html, raw, fmtDate, toast } from "../ui.js";
import { openNote } from "../forms.js";

const SECTIONS = [
  { kind: "dated", heading: "Coming up", blurb: "Dates close enough to do something about." },
  { kind: "quiet", heading: "Open threads gone quiet", blurb: "Still open, nothing written lately." },
  { kind: "drift", heading: "Drifting", blurb: "People you haven't written about in a long while." },
];

function whenBadge(item) {
  if (item.kind === "dated") {
    const soon = item.days_until <= 3;
    const label = item.days_until === 0 ? "today"
      : item.days_until === 1 ? "1 day"
      : `${item.days_until} days`;
    return html`<div class="when ${soon ? "soon" : ""}">${label}</div>`;
  }
  const months = Math.floor((item.silent_days ?? 0) / 30);
  const label = months >= 2 ? `${months} mo` : `${item.silent_days}d`;
  return html`<div class="when stale">${label}<br><span style="font-weight:400">quiet</span></div>`;
}

function itemMarkup(item) {
  const dateLine = item.date ? ` · ${fmtDate(item.date)}` : "";
  return html`
    <article class="item" data-key="${item.key}">
      ${raw(whenBadge(item))}
      <div class="item-body">
        <div class="who">
          <a href="#/person/${item.person_id}">${item.person_name}</a>${raw(dateLine)}
        </div>
        <div class="what">${item.title}</div>
        ${item.context ? raw(html`<div class="why">${item.context}</div>`) : ""}
        <div class="item-actions">
          <button class="link" data-act="note"
                  data-person="${item.person_id}" data-name="${item.person_name}">Write a note</button>
          <button class="link" data-act="snooze">Snooze a week</button>
          ${item.event_id && item.kind === "dated"
            ? raw(html`<button class="link" data-act="done" data-event="${item.event_id}"
                               data-recurrence="${item.recurrence}"
                               data-days="${item.days_until}">${
                 item.recurrence === "none" ? "Mark done" : "Done this time"}</button>`)
            : ""}
        </div>
      </div>
    </article>`;
}

export async function render(mount) {
  mount.innerHTML = `<p class="muted">Loading…</p>`;
  const review = await api.review();
  const { items } = review;

  const heading = html`
    <div class="review-head">
      <h1>This week</h1>
      <p class="muted">${items.length === 0
        ? "Nothing needs you right now."
        : `${items.length} thing${items.length === 1 ? "" : "s"} worth your attention.`}</p>
    </div>`;

  if (items.length === 0) {
    mount.innerHTML = heading + html`
      <div class="card empty">
        <p>You're on top of everyone.</p>
        <p class="muted" style="margin-top:6px">
          Come back next week, or <a href="#/people">look through your people</a>.
        </p>
      </div>`;
    return;
  }

  const sections = SECTIONS.map(({ kind, heading: title, blurb }) => {
    const group = items.filter((i) => i.kind === kind);
    if (group.length === 0) return "";
    return html`
      <div class="section-head">
        <h2>${title}</h2>
        <span class="muted" style="font-size:.8rem">${blurb}</span>
      </div>
      ${raw(group.map(itemMarkup).join(""))}`;
  }).join("");

  mount.innerHTML = heading + sections;

  mount.onclick = async (e) => {
    const button = e.target.closest("button[data-act]");
    if (!button) return;
    const card = button.closest(".item");
    const key = card.dataset.key;

    try {
      if (button.dataset.act === "note") {
        openNote({
          personId: Number(button.dataset.person),
          personName: button.dataset.name,
          onDone: () => render(mount),
        });
      } else if (button.dataset.act === "snooze") {
        await api.dismiss(key, 7);
        card.remove();
        toast("Snoozed for a week");
      } else if (button.dataset.act === "done") {
        // A one-off is retired for good. A repeat is never finished, so only
        // this occurrence is cleared — the key already names its date.
        if (button.dataset.recurrence === "none") {
          await api.updateEvent(Number(button.dataset.event), { done: true });
          toast("Marked done");
        } else {
          await api.dismiss(key, Number(button.dataset.days) + 1);
          toast("Cleared until the next one");
        }
        card.remove();
      }
    } catch (err) {
      toast(err.message);
    }
  };
}
