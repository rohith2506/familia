import { api } from "../api.js";
import { html, raw, toast } from "../ui.js";

const FIELDS = [
  { key: "birthday_lead_days", label: "Warn me about birthdays this many days ahead",
    hint: "Long enough to actually do something about it." },
  { key: "thread_quiet_days", label: "Flag an open thread after this many quiet days",
    hint: "No note written against the thread in this long." },
  { key: "person_quiet_days", label: "Flag a person after this many quiet days",
    hint: "Only applies to people with no open threads." },
  { key: "review_horizon_days", label: "Never surface anything further out than",
    hint: "A ceiling on how far ahead the review looks, whatever an event's lead time says." },
];

export async function render(mount) {
  mount.innerHTML = `<p class="muted">Loading…</p>`;
  const settings = await api.settings();

  mount.innerHTML = html`
    <div class="review-head">
      <h1>Settings</h1>
      <p class="muted">What the weekly review considers worth raising.</p>
    </div>
    <form class="card" id="settings">
      ${raw(FIELDS.map((f) => html`
        <label for="${f.key}">${f.label}</label>
        <input id="${f.key}" name="${f.key}" type="number" min="1" max="365" value="${settings[f.key]}">
        <p class="muted" style="font-size:.8rem;margin-top:4px">${f.hint}</p>`).join(""))}
      <div class="row" style="justify-content:flex-end;margin-top:18px">
        <button type="submit">Save</button>
      </div>
    </form>

    <form method="post" action="/logout" class="row" style="justify-content:flex-end">
      <button type="submit" class="ghost">Sign out</button>
    </form>`;

  mount.querySelector("#settings").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    try {
      await api.saveSettings(data);
      toast("Saved");
    } catch (err) {
      toast(err.message);
    }
  };
}
