let LISTS = {};
let TAG_COLORS = {};


// ═══════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════
const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

let state = {
  activeList: null,
  lb: 3,
  topN: 3,
  view: "r",
  cache: {},       // { listId: { ticker: [points] } }
  fxCache: {},     // { "EURUSD=X": [points], etc }
  currentView: "home",   // "home" or "list"
  typeFilter: "All",
};

let GLOBAL_BASE_CURRENCY = "USD";

// ═══════════════════════════════════════════
//  MOBILE NAV
// ═══════════════════════════════════════════
function toggleMobileNav() {
  document.getElementById("mobile-nav-toggle").classList.toggle("open");
  document.getElementById("mobile-nav-backdrop").classList.toggle("open");
  document.getElementById("sidebar").classList.toggle("open");
}

function closeMobileNav() {
  document.getElementById("mobile-nav-toggle").classList.remove("open");
  document.getElementById("mobile-nav-backdrop").classList.remove("open");
  document.getElementById("sidebar").classList.remove("open");
}

// ═══════════════════════════════════════════
//  SIDEBAR
// ═══════════════════════════════════════════
function buildSidebar() {
  const nav = document.getElementById("sidebar");
  let html = `<button class="sidebar-home-btn${state.currentView === 'home' ? ' active' : ''}" onclick="showHome()">MarketDeck</button>`;

  const grouped = {};
  for (const [id, list] of Object.entries(LISTS)) {
    if (!grouped[list.category]) grouped[list.category] = [];
    grouped[list.category].push({ id, list });
  }

  for (const cat in grouped) {
    html += `<div class="sidebar-section">${cat}</div>`;
    for (const item of grouped[cat]) {
      const id = item.id;
      const list = item.list;
      html += `<button class="list-btn${state.activeList === id && state.currentView === 'list' ? ' active' : ''}" data-list="${id}" onclick="switchList('${id}')">
        <span>${list.shortName}</span>
        <span class="count">${list.items.length}</span>
      </button>`;
    }
  }
  nav.innerHTML = html;
}

// ═══════════════════════════════════════════
//  NAVIGATION
// ═══════════════════════════════════════════
function showHome() {
  closeMobileNav();
  state.currentView = "home";
  state.activeList = null;
  document.getElementById("view-home").style.display = "block";
  document.getElementById("view-list").style.display = "none";
  closeEditor();
  buildSidebar();
  renderHomepage();
}

function switchList(id) {
  closeMobileNav();
  state.currentView = "list";
  state.activeList = id;

  document.getElementById("view-home").style.display = "none";
  document.getElementById("view-list").style.display = "block";

  state.typeFilter = "All"; // Reset filter on list switch

  buildSidebar();

  const list = LISTS[id];
  document.getElementById("page-title").textContent = list.name;
  document.getElementById("page-subtitle").textContent = list.description;

  // reset view
  state.view = "r";
  document.getElementById("tab-r").className = "a-purple";
  document.getElementById("tab-h").className = "";
  document.getElementById("view-r").style.display = "block";
  document.getElementById("view-h").style.display = "none";

  loadData(id);
}

// ═══════════════════════════════════════════
//  HOMEPAGE
// ═══════════════════════════════════════════
function renderHomepage() {
  document.getElementById("home-currency-input").value = GLOBAL_BASE_CURRENCY;

  // Render watchlist cards
  const grid = document.getElementById("home-grid");
  let html = "";
  for (const [id, list] of Object.entries(LISTS)) {
    html += `<div class="wl-card" onclick="switchList('${id}')">
      <button class="wl-card-edit" onclick="event.stopPropagation();openListEditModal('${id}')" title="Edit list">✎</button>
      <div class="wl-card-name">${list.name}</div>
      <div class="wl-card-meta">
        <span class="wl-card-count">${list.items.length} tickers</span>
        <span class="wl-card-category">${list.category}</span>
      </div>
      ${list.description ? `<div class="wl-card-desc">${list.description}</div>` : ""}
    </div>`;
  }
  html += `<div class="wl-card-new" onclick="openCreateListModal()">
    <div class="wl-card-new-icon">+</div>
    <div class="wl-card-new-label">Create New List</div>
  </div>`;
  grid.innerHTML = html;

  // Render tag colors editor
  renderTagColorsEditor();
}

// ═══════════════════════════════════════════
//  TAG COLOR EDITOR
// ═══════════════════════════════════════════
function autoGenerateTagColors(hex) {
  // From a single hex color, generate bg (12% opacity), text (full), border (30% opacity)
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return {
    bg: `rgba(${r},${g},${b},0.12)`,
    text: hex,
    border: `rgba(${r},${g},${b},0.30)`
  };
}

function hexFromTagColors(tc) {
  // Try to extract the hex from the text color
  if (tc.text && tc.text.startsWith("#")) return tc.text;
  // Fallback: try to parse rgb
  const m = tc.text && tc.text.match(/(\d+),\s*(\d+),\s*(\d+)/);
  if (m) {
    const toHex = n => parseInt(n).toString(16).padStart(2, "0");
    return `#${toHex(m[1])}${toHex(m[2])}${toHex(m[3])}`;
  }
  return "#68d391";
}

function renderTagColorsEditor() {
  const container = document.getElementById("tag-colors-editor");
  let html = `<div class="tag-color-grid">`;
  for (const [tag, colors] of Object.entries(TAG_COLORS)) {
    const hex = hexFromTagColors(colors);
    const preview = autoGenerateTagColors(hex);
    html += `<div class="tag-color-row">
      <span class="tag-color-preview" style="background:${preview.bg};color:${preview.text};border:1px solid ${preview.border}">${tag}</span>
      <input type="color" class="tag-color-input" value="${hex}" data-tag="${tag}" onchange="updateTagColor('${tag}', this.value)" />
      <button class="tag-color-del" onclick="deleteTagColor('${tag}')" title="Delete">✕</button>
    </div>`;
  }
  html += `</div>`;
  container.innerHTML = html;
}

async function updateTagColor(tag, hex) {
  const colors = autoGenerateTagColors(hex);
  try {
    await fetch(`/api/tag-colors/${encodeURIComponent(tag)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(colors)
    });
    TAG_COLORS[tag] = colors;
    renderTagColorsEditor();
  } catch (e) { alert("Error: " + e.message); }
}

async function deleteTagColor(tag) {
  if (!confirm(`Remove color for "${tag}"?`)) return;
  try {
    await fetch(`/api/tag-colors/${encodeURIComponent(tag)}`, { method: "DELETE" });
    delete TAG_COLORS[tag];
    renderTagColorsEditor();
  } catch (e) { alert("Error: " + e.message); }
}

async function addTagColor() {
  const name = document.getElementById("tag-new-name").value.trim();
  const hex = document.getElementById("tag-new-color").value;
  if (!name) return alert("Tag name is required.");
  const colors = autoGenerateTagColors(hex);
  try {
    await fetch(`/api/tag-colors/${encodeURIComponent(name)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(colors)
    });
    TAG_COLORS[name] = colors;
    document.getElementById("tag-new-name").value = "";
    renderTagColorsEditor();
  } catch (e) { alert("Error: " + e.message); }
}

// ═══════════════════════════════════════════
//  LIST EDIT MODAL
// ═══════════════════════════════════════════
let _editingListSlug = null;

function openListEditModal(slug) {
  _editingListSlug = slug;
  const list = LISTS[slug];
  document.getElementById("list-edit-title").textContent = `Edit: ${list.name}`;
  document.getElementById("le-name").value = list.name;
  document.getElementById("le-short").value = list.shortName;
  document.getElementById("le-category").value = list.category;
  document.getElementById("le-show-type").checked = list.showType !== false;
  document.getElementById("le-desc").value = list.description;
  document.querySelector("#list-edit-modal .btn-red").style.display = "";
  document.getElementById("list-edit-modal").style.display = "block";
}

function closeListEditModal() {
  _editingListSlug = null;
  document.getElementById("list-edit-modal").style.display = "none";
}

function openCreateListModal() {
  _editingListSlug = "__new__";
  document.getElementById("list-edit-title").textContent = "Create New List";
  document.getElementById("le-name").value = "";
  document.getElementById("le-short").value = "";
  document.getElementById("le-category").value = "";
  document.getElementById("le-show-type").checked = true;
  document.getElementById("le-desc").value = "";
  // Hide delete button for new lists
  document.querySelector("#list-edit-modal .btn-red").style.display = "none";
  document.getElementById("list-edit-modal").style.display = "block";
}

async function saveListFromModal() {
  const name = document.getElementById("le-name").value.trim();
  const short_name = document.getElementById("le-short").value.trim();
  const category = document.getElementById("le-category").value.trim() || "Other";
  const show_type = document.getElementById("le-show-type").checked;
  const description = document.getElementById("le-desc").value.trim();

  if (!name || !short_name) return alert("Name and Short Name are required.");

  if (_editingListSlug === "__new__") {
    // Create new list — auto-generate slug from short_name
    const slug = short_name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    if (!slug) return alert("Short Name must contain letters or numbers.");
    try {
      await fetch("/api/lists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug, name, short_name, category, description, tag: "", currency: GLOBAL_BASE_CURRENCY, show_type })
      });
      closeListEditModal();
      await refreshApp();
    } catch (e) { alert("Error: " + e.message); }
  } else {
    // Update existing
    try {
      await fetch(`/api/lists/${_editingListSlug}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, short_name, category, description, tag: LISTS[_editingListSlug]?.tag || "", show_type })
      });
      closeListEditModal();
      await refreshApp();
    } catch (e) { alert("Error: " + e.message); }
  }
}

async function deleteListFromModal() {
  if (!_editingListSlug || _editingListSlug === "__new__") return;
  if (!confirm(`Delete the entire "${LISTS[_editingListSlug].name}" list?`)) return;
  try {
    await fetch(`/api/lists/${_editingListSlug}`, { method: "DELETE" });
    closeListEditModal();
    await refreshApp();
  } catch (e) { alert("Error: " + e.message); }
}

// ═══════════════════════════════════════════
//  UTILS
// ═══════════════════════════════════════════
function fmtPct(v) {
  if (v === null || v === undefined) return "—";
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}
function retTextColor(v) { return (!v && v !== 0) ? "#718096" : v >= 0 ? "#68d391" : "#fc8181"; }
function retBgColor(v) {
  if (v === null || v === undefined) return "#4a5568";
  if (v > 4) return "#38a169";
  if (v > 2) return "#68d391";
  if (v > 0) return "#9ae6b4";
  if (v > -2) return "#fc8181";
  if (v > -4) return "#e53e3e";
  return "#9b2c2c";
}
function currencySymbol(c) {
  const formatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: c, minimumFractionDigits: 0, maximumFractionDigits: 0 });
  return formatter.format(0).replace(/\d/g, '').trim();
}

function getTagStyle(tag) {
  const c = TAG_COLORS[tag];
  if (c) return `background:${c.bg};color:${c.text};border:1px solid ${c.border}`;

  // Hardcoded fallback for "Other" or any unknown tag
  return `background:rgba(160, 174, 192, 0.1);color:#a0aec0;border:1px solid rgba(160, 174, 192, 0.25)`;
}

function setStatus(html, type) {
  const bar = document.getElementById("status-bar");
  const txt = document.getElementById("status-text");
  bar.className = "s-" + type;
  bar.querySelector(".spinner").style.display = type === "load" ? "block" : "none";
  txt.innerHTML = html;
}

// Parse API response points (date strings → Date objects)
function parsePoints(arr) {
  if (!arr) return null;
  return arr.map(p => ({ date: new Date(p.date), close: p.close }))
    .filter(p => p.close !== null && !isNaN(p.close));
}

function closestAfter(points, targetDate) {
  for (let i = 0; i < points.length; i++) {
    if (points[i].date >= targetDate) return points[i];
  }
  return points[points.length - 1];
}

function getMonthlyReturns(points) {
  const today = new Date();
  const months = [];
  for (let m = 12; m >= 1; m--) {
    const d = new Date(today.getFullYear(), today.getMonth() - m, 1);
    const monthLabel = MONTH_LABELS[d.getMonth()] + " " + String(d.getFullYear()).slice(2);
    const nextMonth = new Date(d.getFullYear(), d.getMonth() + 1, 1);
    const inMonth = points.filter(p => p.date >= d && p.date < nextMonth);
    if (inMonth.length === 0) { months.push({ label: monthLabel, ret: null }); continue; }
    const prevMonthStart = new Date(d.getFullYear(), d.getMonth() - 1, 1);
    const inPrevMonth = points.filter(p => p.date >= prevMonthStart && p.date < d);
    if (inPrevMonth.length === 0) { months.push({ label: monthLabel, ret: null }); continue; }
    const prevClose = inPrevMonth[inPrevMonth.length - 1].close;
    const thisClose = inMonth[inMonth.length - 1].close;
    months.push({ label: monthLabel, ret: +((thisClose / prevClose - 1) * 100).toFixed(2) });
  }
  return months;
}

// ═══════════════════════════════════════════
//  LOAD DATA (server-side via /api/prices)
// ═══════════════════════════════════════════
async function loadData(listId) {
  const list = LISTS[listId];
  const sb = document.getElementById("status-bar");
  sb.querySelector(".spinner").style.display = "block";
  sb.className = "s-load";
  document.getElementById("status-text").textContent = `Fetching live data for ${list.shortName}…`;
  document.getElementById("app").style.display = "none";

  // Use cache if available
  if (state.cache[listId]) {
    finishLoad(listId);
    return;
  }

  state.cache[listId] = {};
  try {
    // 1. Identify all tickers + FX pairs needed
    const stockTickers = list.items.map(s => s.ticker);

    const foreignCurrencies = [...new Set(
      list.items
        .map(s => s.currency)
        .filter(c => c && c !== GLOBAL_BASE_CURRENCY && c !== "USX")
    )];

    const fxTickers = foreignCurrencies.map(cur => {
      const prefix = cur === "GBp" ? "GBP" : cur;
      return `${prefix}${GLOBAL_BASE_CURRENCY}=X`;
    }).filter(t => !state.fxCache[t]); // skip already cached FX

    const allTickers = [...stockTickers, ...fxTickers];

    if (state.activeList === listId) {
      document.getElementById("status-text").textContent = `Fetching ${stockTickers.length} tickers + ${fxTickers.length} FX rates…`;
    }

    // 2. Single batch request to server
    const res = await fetch("/api/prices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers: allTickers })
    });
    const priceData = await res.json();

    // 3. Populate caches
    stockTickers.forEach(t => {
      state.cache[listId][t] = parsePoints(priceData[t]);
    });

    fxTickers.forEach(t => {
      state.fxCache[t] = parsePoints(priceData[t]);
    });

    if (state.activeList === listId) finishLoad(listId);
  } catch (e) {
    if (state.activeList === listId) {
      sb.className = "s-err";
      sb.querySelector(".spinner").style.display = "none";
      document.getElementById("status-text").innerHTML =
        "⚠ " + e.message + ` <button class="retry-btn" onclick="delete state.cache['${listId}'];loadData('${listId}')">↻ Retry</button>`;
    }
  }
}

function finishLoad(listId) {
  const sb = document.getElementById("status-bar");
  const cache = state.cache[listId];
  const list = LISTS[listId];
  const failed = list.items.filter(s => !cache[s.ticker]);
  const ok = list.items.length - failed.length;

  document.getElementById("updated-label").textContent = "Updated: " + new Date().toLocaleTimeString();
  sb.className = "s-ok";
  sb.querySelector(".spinner").style.display = "none";

  let statusMsg = `✓ ${ok}/${list.items.length} tickers loaded`;
  if (failed.length > 0) {
    statusMsg += ` · ${failed.length} failed: ${failed.map(s => s.ticker).join(", ")}`;
    sb.className = "s-load"; // yellowish hint
  }
  document.getElementById("status-text").textContent = statusMsg;

  document.getElementById("app").style.display = "block";
  buildControls();
  render();
}

// ═══════════════════════════════════════════
//  CONTROLS
// ═══════════════════════════════════════════
function buildControls() {
  const lb = document.getElementById("lb-btns");
  lb.innerHTML = "";
  [1, 3, 6, 12].forEach(n => {
    const b = document.createElement("button");
    b.textContent = n + "M"; b.id = "lb" + n;
    if (n === state.lb) b.className = "a-amber";
    b.onclick = () => { state.lb = n;[1, 3, 6, 12].forEach(x => { document.getElementById("lb" + x).className = x === n ? "a-amber" : ""; }); render(); };
    lb.appendChild(b);
  });
  const tn = document.getElementById("tn-btns");
  tn.innerHTML = "";
  [1, 2, 3, 4, 5].forEach(n => {
    const b = document.createElement("button");
    b.textContent = n; b.id = "tn" + n;
    if (n === state.topN) b.className = "a-blue";
    b.onclick = () => { state.topN = n;[1, 2, 3, 4, 5].forEach(x => { document.getElementById("tn" + x).className = x === n ? "a-blue" : ""; }); render(); };
    tn.appendChild(b);
  });

  const typeCg = document.getElementById("type-filter-cg");
  const typeSelect = document.getElementById("type-filter-select");
  const list = LISTS[state.activeList];
  if (list && list.showType !== false) {
    typeCg.style.display = "";

    // Get unique tags
    const tags = new Set(list.items.map(item => item.tag).filter(t => t));
    const sortedTags = Array.from(tags).sort();

    let optionsHtml = `<option value="All">All Types</option>\n`;
    sortedTags.forEach(tag => {
      optionsHtml += `<option value="${tag}">${tag}</option>\n`;
    });
    typeSelect.innerHTML = optionsHtml;
    typeSelect.value = state.typeFilter;
  } else {
    typeCg.style.display = "none";
  }
}

function setView(v) {
  state.view = v;
  document.getElementById("view-r").style.display = v === "r" ? "block" : "none";
  document.getElementById("view-h").style.display = v === "h" ? "block" : "none";
  document.getElementById("tab-r").className = v === "r" ? "a-purple" : "";
  document.getElementById("tab-h").className = v === "h" ? "a-purple" : "";
}

function setTypeFilter(val) {
  state.typeFilter = val;
  render();
}

// ═══════════════════════════════════════════
//  COMPUTE & RENDER
// ═══════════════════════════════════════════
function getScored() {
  const listId = state.activeList;
  const list = LISTS[listId];
  const cache = state.cache[listId] || {};
  const today = new Date();

  return list.items.map(s => {
    let pts = cache[s.ticker];
    if (!pts || pts.length < 2) return { ...s, score: null, currentPrice: null, basePrice: null, baseDate: null, monthly: [] };

    if (!pts._processed) {
      pts._processed = true;
      let processedPts = pts;

      // -- Currency Conversion Transformation --
      if (s.currency && s.currency !== GLOBAL_BASE_CURRENCY) {
        if (s.currency === "USX") {
          // Special case: US Cents to US Dollars
          processedPts = pts.map(p => ({ date: p.date, close: p.close / 100 }));
        } else {
          let fxPrefix = s.currency;
          if (s.currency === "GBp") fxPrefix = "GBP";

          const fxTicker = `${fxPrefix}${GLOBAL_BASE_CURRENCY}=X`;
          const fxPts = state.fxCache[fxTicker];
          if (fxPts && fxPts.length > 0) {
            let fxIdx = 0;
            processedPts = pts.map(p => {
              while (fxIdx < fxPts.length - 1 && fxPts[fxIdx + 1].date <= p.date) {
                fxIdx++;
              }
              let rate = fxPts[fxIdx].close;

              let finalRate = rate;
              if (s.currency === "GBp") {
                finalRate = rate / 100;
              }

              return { date: p.date, close: p.close * finalRate };
            });
          }
        }
      }

      pts._processedPts = processedPts;

      const currentPt = processedPts[processedPts.length - 1];

      // For the Heatmap's fixed 12M column
      const targetDate12 = new Date(today.getFullYear(), today.getMonth() - 12, today.getDate());
      const basePt12 = closestAfter(processedPts, targetDate12);
      pts._ret12m = (basePt12 && basePt12 !== currentPt) ? +((currentPt.close / basePt12.close - 1) * 100).toFixed(2) : null;

      pts._monthly = getMonthlyReturns(processedPts);
    }

    const processedPts = pts._processedPts;
    const currentPt = processedPts[processedPts.length - 1];

    // For rankings (variable lookback)
    const targetDate = new Date(today.getFullYear(), today.getMonth() - state.lb, today.getDate());
    const basePt = closestAfter(processedPts, targetDate);
    if (!basePt || basePt === currentPt) {
      return { ...s, score: null, currentPrice: currentPt.close, basePrice: null, baseDate: null, monthly: pts._monthly, ret12m: pts._ret12m };
    }
    const score = +((currentPt.close / basePt.close - 1) * 100).toFixed(2);

    return { ...s, score, currentPrice: currentPt.close, basePrice: basePt.close, baseDate: basePt.date, monthly: pts._monthly, ret12m: pts._ret12m };
  });
}

function render() {
  if (!state.activeList) return;
  const list = LISTS[state.activeList];
  const sym = currencySymbol(GLOBAL_BASE_CURRENCY);
  let scored = getScored();

  // Apply type filter
  if (state.typeFilter !== "All") {
    scored = scored.filter(s => s.tag === state.typeFilter);
  }

  const ranked = scored.filter(s => s.score !== null).sort((a, b) => b.score - a.score).map((s, i) => ({ ...s, rank: i + 1 }));
  const missing = scored.filter(s => s.score === null).map((s, i) => ({ ...s, rank: ranked.length + i + 1 }));
  const all = [...ranked, ...missing];
  const selected = ranked.filter(s => s.rank <= state.topN);

  // Method note
  const today = new Date();
  const targetDate = new Date(today.getFullYear(), today.getMonth() - state.lb, today.getDate());
  document.getElementById("method-note").textContent =
    "Return = (today's adj. close) ÷ (adj. close on " + targetDate.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) + ") − 1  ·  " + state.lb + "M momentum  ·  BASE CURRENCY: " + GLOBAL_BASE_CURRENCY;

  // Banner
  document.getElementById("banner-lbl").textContent =
    "Current Holdings — Top " + state.topN + " by " + state.lb + "M Momentum · Equal Weight " + (100 / state.topN).toFixed(0) + "% each";
  const hEl = document.getElementById("holdings");
  hEl.innerHTML = "";
  selected.forEach(s => {
    hEl.innerHTML += `<div class="hcard">
      <div>
        <div style="font-weight: 400;font-size:14px;color:#68d391">${s.ticker}</div>
        <div style="font-size:11px;color:#718096">${s.name}</div>
      </div>
      <div style="font-family:'Google Sans Code', monospace;font-size:13px;margin-left:8px;color:${retTextColor(s.score)}">${fmtPct(s.score)}</div>
    </div>`;
  });

  // Hide/Show 'Type' column header
  const thType = document.getElementById("r-th-type");
  if (thType) thType.style.display = list.showType === false ? "none" : "";

  document.getElementById("ret-hdr").textContent = state.lb + "M Return";

  // Rankings table
  const tbody = document.getElementById("r-body");
  tbody.innerHTML = "";
  all.forEach((s, i) => {
    const isBuy = s.rank <= state.topN && s.score !== null;
    const rowBg = isBuy ? "rgba(255, 255, 255, 0.03)" : "transparent";
    const bCls = isBuy ? "rb-buy" : (s.rank <= state.topN + 2 ? "rb-near" : "rb-rest");
    const barPct = s.score !== null ? Math.min(Math.abs(s.score) / 25 * 100, 100) : 0;
    const barCol = s.score !== null && s.score >= 0 ? "#68d391" : "#fc8181";
    const priceStr = s.currentPrice ? sym + s.currentPrice.toFixed(2) : "—";
    const baseDateStr = s.baseDate ? s.baseDate.toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "";
    const typeCellStyle = list.showType === false ? 'style="display:none"' : "";
    tbody.innerHTML += `<tr style="background:${rowBg}">
      <td><span class="rb ${bCls}">${s.rank}</span></td>
      <td><div style="display:flex;align-items:center;gap:8px"><span>${s.name}</span></div></td>
      <td><span class="ticker">${s.ticker}</span></td>
      <td ${typeCellStyle}><span class="tag" style="${getTagStyle(s.tag)}">${s.tag}</span></td>
      <td>
        <div class="bar-wrap">
          <div class="bar-track"><div class="bar-fill" style="width:${barPct}%;background:${barCol}"></div></div>
          <span class="mono" style="font-weight: 400;color:${retTextColor(s.score)}">${fmtPct(s.score)}</span>
        </div>
        ${s.basePrice ? `<div class="price-info">from ${sym}${s.basePrice.toFixed(2)} on ${baseDateStr}</div>` : ""}
      </td>
      <td><span class="mono" style="color:#a0aec0">${priceStr}</span></td>
      <td>${isBuy ? '<span class="sig-buy">● BUY</span>' : '<span class="sig-skip">○ SKIP</span>'}</td>
    </tr>`;
  });

  // Heatmap
  const allMonthLabels = ranked[0]?.monthly?.map(m => m.label) || [];
  const hmHdr = document.getElementById("hm-hdr");
  hmHdr.innerHTML = `<th style="font-family:'Google Sans Code', monospace;padding:16px 20px;text-align:left;background:transparent;border-bottom:1px solid var(--border-subtle);font-size:10px;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.15em;min-width:165px">Name</th>`;
  allMonthLabels.forEach(m => {
    hmHdr.innerHTML += `<th style="font-family:'Google Sans Code', monospace;padding:16px 6px;text-align:center;background:transparent;border-bottom:1px solid var(--border-subtle);font-size:10px;color:var(--text-tertiary);text-transform:uppercase;min-width:48px">${m}</th>`;
  });
  hmHdr.innerHTML += `<th style="font-family:'Google Sans Code', monospace;padding:16px 10px;text-align:center;background:transparent;border-bottom:1px solid var(--border-subtle);font-size:10px;color:var(--accent-positive);text-transform:uppercase;letter-spacing:.15em">12M</th>`;

  const hmBody = document.getElementById("hm-body");
  hmBody.innerHTML = "";
  all.forEach((s, i) => {
    const isBuy = s.rank <= state.topN && s.score !== null;
    const rowBg = isBuy ? "rgba(255, 255, 255, 0.03)" : "transparent";
    const total12m = s.ret12m;
    let cells = "";
    if (s.monthly.length > 0) {
      s.monthly.forEach(m => {
        const bg = m.ret !== null ? retBgColor(m.ret) + "22" : "transparent";
        const tc = m.ret !== null ? retBgColor(m.ret) : "#4a5568";
        const valStr = m.ret !== null ? (m.ret > 0 ? "+" : "") + m.ret.toFixed(1) : "—";
        cells += `<td class="hm-cell"><span class="heatmap-pill" style="background:${bg};color:${tc}">${valStr}</span></td>`;
      });
    } else {
      cells = `<td colspan="${allMonthLabels.length}" style="text-align:center;color:#4a5568;font-size:12px;padding:10px">No data</td>`;
    }
    hmBody.innerHTML += `<tr style="border-bottom:1px solid var(--border-subtle); background:${rowBg}">
      <td style="padding:14px 20px;white-space:nowrap;border-bottom:1px solid var(--border-subtle)">
        <div style="display:flex;align-items:center;gap:8px">
          <div>
            <div class="ticker" style="font-size:12px">${s.ticker}</div>
            <div style="font-size:11px;color:#4a5568">${s.name}</div>
          </div>
        </div>
      </td>
      ${cells}
      <td style="padding:14px 20px;text-align:center;border-bottom:1px solid var(--border-subtle);font-family:'Google Sans Code', monospace;font-size:12px;color:${retTextColor(total12m)}">${total12m !== null ? fmtPct(total12m) : "—"}</td>
    </tr>`;
  });

  // Preserve the currently active view
  setView(state.view);
}

// ═══════════════════════════════════════════
//  TICKER EDITOR (simplified — tickers only)
// ═══════════════════════════════════════════
function openEditor() {
  if (!state.activeList) return;
  const slug = state.activeList;
  const list = LISTS[slug];
  document.getElementById("ed-list-name-label").textContent = list.name;
  renderEditorTickers();
  document.getElementById("editor-overlay").style.display = "block";
}

function closeEditor() {
  document.getElementById("editor-overlay").style.display = "none";
  if (state.activeList) {
    loadData(state.activeList);
  }
}

function renderEditorTickers() {
  const slug = state.activeList;
  const list = LISTS[slug];
  const container = document.getElementById("ed-tickers");
  container.innerHTML = "";

  list.items.forEach((t, i) => {
    const row = document.createElement("div");
    row.className = "ed-ticker-row";
    row.innerHTML = `
      <span style="color:#4a5568;font-size:10px;width:24px;">${i + 1}</span>
      <input class="ed-sym" value="${t.ticker}" data-id="${t.id}" data-field="symbol" />
      <input class="ed-name" value="${t.name}" data-id="${t.id}" data-field="name" />
      <input class="ed-tag" value="${t.tag}" data-id="${t.id}" data-field="tag" />
      <input class="ed-cur" value="${t.currency}" data-id="${t.id}" data-field="currency" maxlength="3" />
      <button class="ed-btn-save" onclick="saveTicker(${t.id}, this)">Save</button>
      <button class="ed-btn-del" onclick="deleteTicker(${t.id})">✕</button>
    `;
    container.appendChild(row);
  });
}

// ═══════════════════════════════════════════
//  GLOBAL SETTINGS
// ═══════════════════════════════════════════
async function saveBaseCurrency() {
  const val = document.getElementById("home-currency-input").value;
  try {
    await fetch("/api/settings/GLOBAL_BASE_CURRENCY", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: val })
    });
    // Also clear the server-side price cache so FX rates are fetched immediately
    await fetch("/api/prices/cache", { method: "DELETE" });

    GLOBAL_BASE_CURRENCY = val;
    state.cache = {};
    state.fxCache = {};

    // If we're looking at a list, actively reload it
    if (state.currentView === "list" && state.activeList) {
      loadData(state.activeList);
    }
  } catch (e) { alert("Error saving currency: " + e.message); }
}

// ═══════════════════════════════════════════
//  TICKER CRUD
// ═══════════════════════════════════════════
async function loadLists() {
  try {
    const res = await fetch("/api/init");
    const data = await res.json();
    LISTS = data.lists;
    TAG_COLORS = data.tagColors;
    return data.settings;
  } catch (e) {
    console.error("Failed to load lists:", e);
    throw e;
  }
}

async function refreshApp() {
  try {
    const settings = await loadLists();
    GLOBAL_BASE_CURRENCY = settings.GLOBAL_BASE_CURRENCY || "USD";

    // clear caches since data changed
    state.cache = {};
    state.fxCache = {};

    buildSidebar();

    if (state.currentView === "home") {
      renderHomepage();
    } else if (state.activeList && LISTS[state.activeList]) {
      // Re-trigger loadData for the active list to sync the UI
      loadData(state.activeList);
    } else {
      showHome();
    }
  } catch (e) {
    console.error("Failed to refresh:", e);
  }
}

async function saveTicker(id, btn) {
  const row = btn.closest(".ed-ticker-row");
  const body = {};
  row.querySelectorAll("input[data-id]").forEach(inp => {
    body[inp.dataset.field] = inp.value;
  });
  try {
    await fetch(`/api/tickers/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    btn.style.borderColor = "#38a169";
    btn.textContent = "✓";
    setTimeout(() => { btn.style.borderColor = "#68d391"; btn.textContent = "Save"; }, 800);

    const list = LISTS[state.activeList];
    const item = list.items.find(t => t.id === id);
    if (item) {
      if (body.symbol) item.ticker = body.symbol;
      if (body.name) item.name = body.name;
      if (body.tag) item.tag = body.tag;
      if (body.currency) item.currency = body.currency;
    }
    delete state.cache[state.activeList];
    state.fxCache = {};
  } catch (e) { alert("Error saving ticker: " + e.message); }
}

async function deleteTicker(id) {
  if (!confirm("Remove this ticker?")) return;
  try {
    await fetch(`/api/tickers/${id}`, { method: "DELETE" });
    const list = LISTS[state.activeList];
    list.items = list.items.filter(t => t.id !== id);
    delete state.cache[state.activeList];
    renderEditorTickers();
    buildSidebar();
  } catch (e) { alert("Error deleting ticker: " + e.message); }
}

async function addTicker() {
  const slug = state.activeList;
  const symbol = document.getElementById("ed-add-symbol").value.trim();
  const name = document.getElementById("ed-add-name").value.trim();
  const tag = document.getElementById("ed-add-tag").value.trim();
  const currency = document.getElementById("ed-add-cur").value.trim().toUpperCase() || "USD";
  if (!symbol || !name) return alert("Symbol and Name are required.");
  try {
    const res = await fetch(`/api/lists/${slug}/tickers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, name, tag, currency })
    });
    const data = await res.json();
    LISTS[slug].items.push({ id: data.id, ticker: symbol, name, tag, currency });
    document.getElementById("ed-add-symbol").value = "";
    document.getElementById("ed-add-name").value = "";
    document.getElementById("ed-add-tag").value = "";
    document.getElementById("ed-add-cur").value = "";
    delete state.cache[slug];
    renderEditorTickers();
    buildSidebar();
  } catch (e) { alert("Error adding ticker: " + e.message); }
}

// ═══════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════
async function initApp() {
  try {
    const res = await fetch('/api/init');
    const data = await res.json();

    LISTS = data.lists;
    TAG_COLORS = data.tagColors;
    GLOBAL_BASE_CURRENCY = data.settings.GLOBAL_BASE_CURRENCY || "USD";

    buildSidebar();
    showHome();
  } catch (e) {
    document.getElementById("view-home").style.display = "block";
    document.getElementById("home-grid").innerHTML = `<div style="color:#fc8181;padding:20px;">Error loading data from server</div>`;
    console.error(e);
  }
}

initApp();
