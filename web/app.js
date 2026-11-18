/* gta6-data SPA — hash routing, relative API paths, no dependencies. */

const VIEWS = ["vehicles", "locations", "prices", "missions"];

const state = {
  vehicles: [],
  locations: [],
  loaded: false,
  error: null,
  query: "",
  cls: "all",
  open: null, // id of the expanded row
};

const $app = document.getElementById("app");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function currentView() {
  const name = location.hash.replace(/^#\/?/, "") || "vehicles";
  return VIEWS.includes(name) ? name : "vehicles";
}

async function loadData() {
  state.error = null;
  try {
    const [vehicles, locations] = await Promise.all([
      "/api/v1/vehicles",
      "/api/v1/locations",
    ].map(async (path) => {
      const res = await fetch(`${path}?limit=5000`);
      if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
      return res.json();
    }));
    state.vehicles = vehicles.records || [];
    state.locations = locations.records || [];
  } catch (err) {
    state.error = err.message;
  }
  state.loaded = true;
  render();
}

function setCounts() {
  document.querySelectorAll("[data-count]").forEach((el) => {
    const ds = el.dataset.count;
    const n = ds === "vehicles" ? state.vehicles.length
      : ds === "locations" ? state.locations.length
      : 0;
    el.textContent = String(n);
  });
}

function evidence(record) {
  const date = (record.updated_at || "").slice(0, 10);
  return `<p class="evidence"><span class="dot" aria-hidden="true"></span><span>source</span>` +
    `<a href="${esc(record.source)}" target="_blank" rel="noopener">${esc(record.source)}</a>` +
    (date ? `<span>· ${esc(date)}</span>` : "") +
    `</p>`;
}

function detailHTML(record) {
  const notes = record.notes
    ? `<p class="notes">${esc(record.notes)}</p>`
    : "";
  return `<div class="detail">${notes}${evidence(record)}</div>`;
}

function vehicleRows() {
  const q = state.query.trim().toLowerCase();
  const cls = state.cls.toLowerCase();
  const rows = state.vehicles.filter((v) => {
    if (cls !== "all" && (v.vehicle_class || "").toLowerCase() !== cls) return false;
    if (!q) return true;
    return `${v.name} ${v.manufacturer || ""}`.toLowerCase().includes(q);
  });
  const list = rows.map((v) => `
    <button type="button" class="row${state.open === v.id ? " open" : ""}" data-id="${esc(v.id)}" aria-expanded="${state.open === v.id}">
      <span><span class="row-name">${esc(v.name)}</span>${v.manufacturer ? `<span class="row-meta"> — ${esc(v.manufacturer)}</span>` : ""}</span>
      <span class="row-kind"><span class="dot" aria-hidden="true"></span>${esc(v.vehicle_class || "Unclassed")}</span>
      ${detailHTML(v)}
    </button>`).join("");
  const classes = [...new Set(state.vehicles.map((v) => v.vehicle_class).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));
  const options = ["all", ...classes].map((c) =>
    `<option value="${esc(c)}"${state.cls === c ? " selected" : ""}>${c === "all" ? "All classes" : esc(c)}</option>`).join("");
  const shown = rows.length === state.vehicles.length && !q && cls === "all"
    ? `${rows.length}`
    : `${rows.length} / ${state.vehicles.length}`;
  return `
    <div class="toolbar">
      <input id="q" type="search" placeholder="Search name or manufacturer" value="${esc(state.query)}" autocomplete="off">
      <select id="cls">${options}</select>
      <span class="total">${shown}</span>
    </div>
    ${rows.length
      ? `<div class="list">${list}</div>`
      : `<div class="empty"><p class="figure">0</p><p class="label">No matches</p></div>`}`;
}

function locationRows() {
  const q = state.query.trim().toLowerCase();
  const rows = state.locations.filter((l) => !q || l.name.toLowerCase().includes(q));
  const list = rows.map((l) => `
    <button type="button" class="row${state.open === l.id ? " open" : ""}" data-id="${esc(l.id)}" aria-expanded="${state.open === l.id}">
      <span class="row-name">${esc(l.name)}</span>
      <span class="row-kind"><span class="dot" aria-hidden="true"></span>${esc(l.kind || "Unknown")}</span>
      ${detailHTML(l)}
    </button>`).join("");
  const shown = rows.length === state.locations.length && !q
    ? `${rows.length}`
    : `${rows.length} / ${state.locations.length}`;
  return `
    <div class="toolbar">
      <input id="q" type="search" placeholder="Search location" value="${esc(state.query)}" autocomplete="off">
      <span class="total">${shown}</span>
    </div>
    ${rows.length
      ? `<div class="list">${list}</div>`
      : `<div class="empty"><p class="figure">0</p><p class="label">No matches</p></div>`}`;
}

function comingSoon(dataset) {
  return `
    <div class="empty">
      <p class="figure">0</p>
      <p class="label">${esc(dataset)}</p>
      <p>Records land when launch-week datamining starts.</p>
    </div>`;
}

function render() {
  setCounts();
  const view = currentView();
  document.querySelectorAll("[data-nav]").forEach((a) => {
    a.setAttribute("aria-current", a.dataset.nav === view ? "true" : "false");
  });
  if (state.error) {
    $app.innerHTML = `
      <div class="error">
        <p>API unreachable (${esc(state.error)}).</p>
        <p><a href="#" data-retry>Retry</a></p>
      </div>`;
    $app.querySelector("[data-retry]").addEventListener("click", (e) => {
      e.preventDefault();
      loadData();
    });
    return;
  }
  if (!state.loaded) {
    $app.innerHTML = `<div class="empty"><p class="label">Loading…</p></div>`;
    return;
  }
  if (view === "vehicles") $app.innerHTML = vehicleRows();
  else if (view === "locations") $app.innerHTML = locationRows();
  else $app.innerHTML = comingSoon(view);

  const input = document.getElementById("q");
  if (input) {
    input.addEventListener("input", () => {
      state.query = input.value;
      // Keep the search box alive while re-rendering.
      const keep = document.activeElement;
      render();
      const again = document.getElementById("q");
      if (keep === input && again) {
        again.focus();
        again.setSelectionRange(again.value.length, again.value.length);
      }
    });
  }
  const select = document.getElementById("cls");
  if (select) {
    select.addEventListener("change", () => {
      state.cls = select.value;
      render();
    });
  }
  $app.querySelectorAll(".row").forEach((row) => {
    row.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      state.open = state.open === row.dataset.id ? null : row.dataset.id;
      render();
    });
  });
}

window.addEventListener("hashchange", () => {
  state.query = "";
  state.cls = "all";
  state.open = null;
  render();
});

if (!state.loaded) loadData();
