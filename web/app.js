/* gta6-data SPA — hash routing, relative API paths, no dependencies. */

const VIEWS = ["vehicles", "locations", "missions", "prices"];

const state = {
  vehicles: [],
  locations: [],
  missions: [],
  prices: [],
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
    // Fetch EVERY view dataset so nav counts and rows are never stale —
    // a dataset added to VIEWS loads automatically with the rest.
    const payloads = await Promise.all(VIEWS.map(async (ds) => {
      const res = await fetch(`/api/v1/${ds}?limit=5000`);
      if (!res.ok) throw new Error(`/api/v1/${ds} -> HTTP ${res.status}`);
      return res.json();
    }));
    VIEWS.forEach((ds, i) => { state[ds] = payloads[i].records || []; });
  } catch (err) {
    state.error = err.message;
  }
  state.loaded = true;
  render();
}

function setCounts() {
  document.querySelectorAll("[data-count]").forEach((el) => {
    // Generic: any dataset present in state gets its live count. The old
    // per-dataset if/chain left every new dataset's badge stuck at 0.
    el.textContent = String((state[el.dataset.count] || []).length);
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

function missionRows() {
  const q = state.query.trim().toLowerCase();
  const rows = state.missions.filter((m) => !q || m.name.toLowerCase().includes(q));
  const list = rows.map((m) => {
    const meta = [m.kind || "Mission", m.reward].filter(Boolean).join(" · ");
    return `
    <button type="button" class="row${state.open === m.id ? " open" : ""}" data-id="${esc(m.id)}" aria-expanded="${state.open === m.id}">
      <span class="row-name">${esc(m.name)}</span>
      <span class="row-kind"><span class="dot" aria-hidden="true"></span>${esc(meta)}</span>
      ${detailHTML(m)}
    </button>`;}).join("");
  const shown = rows.length === state.missions.length && !q
    ? `${rows.length}`
    : `${rows.length} / ${state.missions.length}`;
  return `
    <div class="toolbar">
      <input id="q" type="search" placeholder="Search mission" value="${esc(state.query)}" autocomplete="off">
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
      <p>No records yet — they land as community sources publish them.</p>
    </div>`;
}

// Renderers per dataset. A dataset with real rows MUST appear here;
// test_frontend_parity.py enforces it. prices keeps the coming-soon
// placeholder until a source publishes in-game prices.
const ROW_RENDERERS = {
  vehicles: vehicleRows,
  locations: locationRows,
  missions: missionRows,
};

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
  const renderer = ROW_RENDERERS[view];
  $app.innerHTML = renderer ? renderer() : comingSoon(view);

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
