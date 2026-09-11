// Hash router. Each view owns its own mount point and re-renders itself.

import { toast, esc } from "./ui.js";
import { openNote } from "./forms.js";
import * as review from "./views/review.js";
import * as people from "./views/people.js";
import * as person from "./views/person.js";
import * as settings from "./views/settings.js";
import * as search from "./views/search.js";

const mount = document.getElementById("view");

const ROUTES = [
  { pattern: /^#?\/?$/, nav: "review", run: () => review.render(mount) },
  { pattern: /^#\/people$/, nav: "people", run: () => people.render(mount) },
  { pattern: /^#\/person\/(\d+)$/, nav: "people", run: (m) => person.render(mount, Number(m[1])) },
  { pattern: /^#\/settings$/, nav: "settings", run: () => settings.render(mount) },
  { pattern: /^#\/search\/(.+)$/, nav: null, run: (m) => search.render(mount, decodeURIComponent(m[1])) },
];

let current = null;

async function route() {
  const hash = location.hash || "#/";
  const match = ROUTES.map((r) => ({ r, m: hash.match(r.pattern) })).find((x) => x.m);

  document.querySelectorAll("[data-nav]").forEach((a) => {
    a.classList.toggle("active", Boolean(match) && a.dataset.nav === match.r.nav);
  });

  if (!match) {
    mount.innerHTML = `<div class="card empty"><p>Nothing here.</p></div>`;
    return;
  }

  // Views attach their own mount.onclick; drop the previous one first.
  mount.onclick = null;
  current = match.r;
  try {
    await match.r.run(match.m);
  } catch (err) {
    mount.innerHTML = `<div class="card empty"><p class="error">${esc(err.message)}</p></div>`;
  }
}

const refresh = () => route();

document.getElementById("capture").onclick = () => openNote({ onDone: refresh });

const searchBox = document.getElementById("search");
searchBox.closest("form").onsubmit = (e) => {
  e.preventDefault();
  const q = searchBox.value.trim();
  if (q.length >= 2) location.hash = `#/search/${encodeURIComponent(q)}`;
};

// "n" writes a note, "/" jumps to search — both skipped while typing.
document.addEventListener("keydown", (e) => {
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
  if (typing || e.metaKey || e.ctrlKey || document.querySelector(".backdrop")) return;
  if (e.key === "n") { e.preventDefault(); openNote({ onDone: refresh }); }
  if (e.key === "/") { e.preventDefault(); searchBox.focus(); }
});

window.addEventListener("hashchange", route);
route().catch((err) => toast(err.message));
