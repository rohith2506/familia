// Rendering helpers. `html` escapes every interpolation by default; wrap
// already-built markup in raw() to opt out.

const ENTITIES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ENTITIES[c]);

class Raw {
  constructor(value) { this.value = value; }
}

export const raw = (value) => new Raw(value);

function render(value) {
  if (value instanceof Raw) return value.value;
  if (Array.isArray(value)) return value.map(render).join("");
  if (value === null || value === undefined || value === false) return "";
  return esc(value);
}

export function html(strings, ...values) {
  let out = strings[0];
  for (let i = 0; i < values.length; i++) {
    out += render(values[i]) + strings[i + 1];
  }
  return out;
}

// --- dates ---------------------------------------------------------------

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Parse a bare YYYY-MM-DD as local time; `new Date(iso)` would read it as UTC. */
export function parseISO(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function fmtDate(iso, { withYear = false } = {}) {
  if (!iso) return "";
  const d = parseISO(iso);
  const base = `${MONTHS[d.getMonth()]} ${d.getDate()}`;
  return withYear || d.getFullYear() !== new Date().getFullYear()
    ? `${base}, ${d.getFullYear()}`
    : base;
}

export function fmtDayLabel(iso) {
  const days = Math.round((parseISO(iso) - parseISO(todayISO())) / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days === -1) return "yesterday";
  if (days < 0) return fmtDate(iso);
  return `in ${days}d`;
}

// Mirrors app/review.py — the portrait shows the same next date the weekly
// review computed, so the two screens never disagree.
const STEP_DAYS = { daily: 1, weekly: 7, biweekly: 14 };
const STEP_MONTHS = { monthly: 1, quarterly: 3, yearly: 12 };

export const RECURRENCE_LABELS = {
  daily: "daily", weekly: "weekly", biweekly: "fortnightly",
  monthly: "monthly", quarterly: "quarterly", yearly: "yearly",
};

const toISO = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function addMonths(anchor, months) {
  const total = anchor.getMonth() + months;
  const year = anchor.getFullYear() + Math.floor(total / 12);
  const month = ((total % 12) + 12) % 12;
  // Clamp to the last valid day, the way Python's _safe_date does.
  const lastDay = new Date(year, month + 1, 0).getDate();
  return new Date(year, month, Math.min(anchor.getDate(), lastDay));
}

/** Next date this event falls, or null for a one-off already past. */
export function nextOccurrence(onDate, recurrence) {
  const anchor = parseISO(onDate);
  const today = parseISO(todayISO());
  const isDay = recurrence in STEP_DAYS;
  const isMonth = recurrence in STEP_MONTHS;

  if (!isDay && !isMonth) return anchor >= today ? toISO(anchor) : null;
  if (anchor >= today) return toISO(anchor);

  if (isDay) {
    const step = STEP_DAYS[recurrence];
    const elapsed = Math.round((today - anchor) / 86400000);
    const next = new Date(anchor);
    next.setDate(next.getDate() + Math.ceil(elapsed / step) * step);
    return toISO(next);
  }

  const step = STEP_MONTHS[recurrence];
  const months = (today.getFullYear() - anchor.getFullYear()) * 12 + (today.getMonth() - anchor.getMonth());
  let n = Math.max(0, Math.floor(months / step) * step);
  let candidate = addMonths(anchor, n);
  while (candidate < today) candidate = addMonths(anchor, (n += step));
  return toISO(candidate);
}

export const initials = (name) =>
  String(name).trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");

// --- chrome --------------------------------------------------------------

export function toast(message) {
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = message;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 2600);
}

/**
 * Show a modal. `body` is markup; `onSubmit` receives the <form> and should
 * return truthy to close. Returns a function that closes it early.
 */
export function modal({ title, subtitle = "", body, submitLabel = "Save", onSubmit }) {
  const backdrop = document.createElement("div");
  backdrop.className = "backdrop";
  backdrop.innerHTML = html`
    <div class="modal" role="dialog" aria-modal="true" aria-label="${title}">
      <h2>${title}</h2>
      ${subtitle ? raw(html`<p class="muted">${subtitle}</p>`) : ""}
      <form>
        ${raw(body)}
        <div class="actions">
          <button type="button" class="ghost" data-close>Cancel</button>
          <button type="submit">${submitLabel}</button>
        </div>
      </form>
    </div>`;

  const close = () => {
    backdrop.remove();
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => { if (e.key === "Escape") close(); };

  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop || e.target.hasAttribute("data-close")) close();
  });
  backdrop.querySelector("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = backdrop.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      if (await onSubmit(e.target)) close();
    } catch (err) {
      toast(err.message);
    } finally {
      button.disabled = false;
    }
  });

  document.addEventListener("keydown", onKey);
  document.body.appendChild(backdrop);
  backdrop.querySelector("input, textarea, select")?.focus();
  return close;
}

export function confirmDelete(what) {
  return window.confirm(`Delete ${what}? This can't be undone.`);
}
