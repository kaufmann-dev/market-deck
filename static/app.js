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
};

let GLOBAL_BASE_CURRENCY = "USD";

// ═══════════════════════════════════════════
//  SIDEBAR
// ═══════════════════════════════════════════
function buildSidebar() {
  const nav = document.getElementById("sidebar");
  let html = `<div class="sidebar-title">Watchlists</div>`;
  let lastCat = null;
  for (const [id, list] of Object.entries(LISTS)) {
    if (list.category !== lastCat) {
      html += `<div class="sidebar-section">${list.category}</div>`;
      lastCat = list.category;
    }
    html += `<button class="list-btn" data-list="${id}" onclick="switchList('${id}')">
      <span>${list.shortName}</span>
      <span class="count">${list.items.length}</span>
    </button>`;
  }
  nav.innerHTML = html;
}

function switchList(id) {
  if (state.activeList === id) return;
  state.activeList = id;

  // update sidebar active
  document.querySelectorAll(".list-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.list === id);
  });

  const list = LISTS[id];
  document.getElementById("page-title").textContent = list.name;
  document.getElementById("header-tag").textContent = list.tag;
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
  const c = TAG_COLORS[tag] || TAG_COLORS["Other"] || { bg: "transparent", text: "#a0aec0", border: "transparent" };
  return `background:${c.bg};color:${c.text};border:1px solid ${c.border}`;
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
}

function setView(v) {
  state.view = v;
  document.getElementById("view-r").style.display = v === "r" ? "block" : "none";
  document.getElementById("view-h").style.display = v === "h" ? "block" : "none";
  document.getElementById("tab-r").className = v === "r" ? "a-purple" : "";
  document.getElementById("tab-h").className = v === "h" ? "a-purple" : "";
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

    // -- Currency Conversion Transformation --
    if (s.currency && s.currency !== GLOBAL_BASE_CURRENCY) {
      if (s.currency === "USX") {
        // Special case: US Cents to US Dollars
        pts = pts.map(p => ({ date: p.date, close: p.close / 100 }));
      } else {
        let fxPrefix = s.currency;
        if (s.currency === "GBp") fxPrefix = "GBP";

        const fxTicker = `${fxPrefix}${GLOBAL_BASE_CURRENCY}=X`;
        const fxPts = state.fxCache[fxTicker];
        if (fxPts && fxPts.length > 0) {
          pts = pts.map(p => {
            // Find closest chronological FX rate on or before the stock's date
            // Binary search or simple reverse scan is fine since data is small
            let rate = null;
            for (let i = fxPts.length - 1; i >= 0; i--) {
              if (fxPts[i].date <= p.date) {
                rate = fxPts[i].close;
                break;
              }
            }
            // If no prior rate, use the earliest available
            if (rate === null) rate = fxPts[0].close;

            let finalRate = rate;
            // GBp (pence) requires dividing the rate by 100 since the rate is for GBP (Pounds)
            if (s.currency === "GBp") {
              finalRate = rate / 100;
            }

            return { date: p.date, close: p.close * finalRate };
          });
        }
      }
    }

    const currentPt = pts[pts.length - 1];

    // For rankings (variable lookback)
    const targetDate = new Date(today.getFullYear(), today.getMonth() - state.lb, today.getDate());
    const basePt = closestAfter(pts, targetDate);
    if (!basePt || basePt === currentPt) return { ...s, score: null, currentPrice: currentPt.close, basePrice: null, baseDate: null, monthly: [], ret12m: null };
    const score = +((currentPt.close / basePt.close - 1) * 100).toFixed(2);

    // For the Heatmap's fixed 12M column
    const targetDate12 = new Date(today.getFullYear(), today.getMonth() - 12, today.getDate());
    const basePt12 = closestAfter(pts, targetDate12);
    const ret12m = (basePt12 && basePt12 !== currentPt) ? +((currentPt.close / basePt12.close - 1) * 100).toFixed(2) : null;

    const monthly = getMonthlyReturns(pts);
    return { ...s, score, currentPrice: currentPt.close, basePrice: basePt.close, baseDate: basePt.date, monthly, ret12m };
  });
}

function render() {
  if (!state.activeList) return;
  const list = LISTS[state.activeList];
  const sym = currencySymbol(GLOBAL_BASE_CURRENCY);
  const scored = getScored();
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
        <div style="font-family:monospace;font-weight:600;font-size:14px;color:#68d391">${s.ticker}</div>
        <div style="font-size:11px;color:#718096">${s.name}</div>
      </div>
      <div style="font-family:monospace;font-size:13px;font-weight:600;margin-left:8px;color:${retTextColor(s.score)}">${fmtPct(s.score)}</div>
    </div>`;
  });

  document.getElementById("ret-hdr").textContent = state.lb + "M Return";

  // Rankings table
  const tbody = document.getElementById("r-body");
  tbody.innerHTML = "";
  all.forEach((s, i) => {
    const isBuy = s.rank <= state.topN && s.score !== null;
    const rowBg = isBuy ? "rgba(104,211,145,.04)" : (i % 2 === 0 ? "#0d1117" : "#0f1419");
    const bCls = isBuy ? "rb-buy" : (s.rank <= state.topN + 2 ? "rb-near" : "rb-rest");
    const barPct = s.score !== null ? Math.min(Math.abs(s.score) / 25 * 100, 100) : 0;
    const barCol = s.score !== null && s.score >= 0 ? "#68d391" : "#fc8181";
    const priceStr = s.currentPrice ? sym + s.currentPrice.toFixed(2) : "—";
    const baseDateStr = s.baseDate ? s.baseDate.toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "";
    tbody.innerHTML += `<tr style="background:${rowBg};border-bottom:1px solid #1a202c">
      <td><span class="rb ${bCls}">${s.rank}</span></td>
      <td><div style="display:flex;align-items:center;gap:8px"><span>${s.name}</span></div></td>
      <td><span class="ticker">${s.ticker}</span></td>
      <td><span class="tag" style="${getTagStyle(s.tag)}">${s.tag}</span></td>
      <td>
        <div class="bar-wrap">
          <div class="bar-track"><div class="bar-fill" style="width:${barPct}%;background:${barCol}"></div></div>
          <span class="mono" style="font-weight:600;color:${retTextColor(s.score)}">${fmtPct(s.score)}</span>
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
  hmHdr.innerHTML = `<th style="padding:10px 14px;background:#161b22;border-bottom:1px solid #21262d;font-family:monospace;font-size:11px;color:#4a5568;text-transform:uppercase;letter-spacing:.08em;min-width:165px">Name</th>`;
  allMonthLabels.forEach(m => {
    hmHdr.innerHTML += `<th style="padding:10px 6px;text-align:center;background:#161b22;border-bottom:1px solid #21262d;border-left:1px solid #21262d;font-family:monospace;font-size:10px;color:#4a5568;text-transform:uppercase;min-width:48px">${m}</th>`;
  });
  hmHdr.innerHTML += `<th style="padding:10px 10px;text-align:center;background:#161b22;border-bottom:1px solid #21262d;border-left:1px solid #2d3748;font-family:monospace;font-size:11px;color:#f6ad55;text-transform:uppercase">12M</th>`;

  const hmBody = document.getElementById("hm-body");
  hmBody.innerHTML = "";
  all.forEach((s, i) => {
    const rowBg = i % 2 === 0 ? "#0d1117" : "#0f1419";
    const total12m = s.ret12m;
    let cells = "";
    if (s.monthly.length > 0) {
      s.monthly.forEach(m => {
        const bg = m.ret !== null ? retBgColor(m.ret) + "22" : "#1a202c";
        const tc = m.ret !== null ? retBgColor(m.ret) : "#4a5568";
        cells += `<td class="hm-cell" style="background:${bg};color:${tc}">${m.ret !== null ? (m.ret > 0 ? "+" : "") + m.ret.toFixed(1) : "—"}</td>`;
      });
    } else {
      cells = `<td colspan="${allMonthLabels.length}" style="text-align:center;color:#4a5568;font-family:monospace;font-size:12px;padding:10px">No data</td>`;
    }
    hmBody.innerHTML += `<tr style="border-bottom:1px solid #1a202c">
      <td style="padding:10px 14px;background:${rowBg};white-space:nowrap">
        <div style="display:flex;align-items:center;gap:8px">
          <div>
            <div class="ticker" style="font-size:12px">${s.ticker}</div>
            <div style="font-size:11px;color:#4a5568">${s.name}</div>
          </div>
        </div>
      </td>
      ${cells}
      <td style="padding:10px;text-align:center;background:#161b22;border-left:1px solid #2d3748;font-family:monospace;font-size:12px;font-weight:600;color:${retTextColor(total12m)}">${total12m !== null ? fmtPct(total12m) : "—"}</td>
    </tr>`;
  });
}

// ═══════════════════════════════════════════
//  EDITOR
// ═══════════════════════════════════════════
function openEditor() {
  if (!state.activeList) return;
  const slug = state.activeList;
  const list = LISTS[slug];

  document.getElementById("ed-base-currency").value = GLOBAL_BASE_CURRENCY;
  document.getElementById("ed-list-slug").textContent = slug;
  document.getElementById("ed-list-name").value = list.name;
  document.getElementById("ed-list-short").value = list.shortName;
  document.getElementById("ed-list-category").value = list.category;
  document.getElementById("ed-list-tag").value = list.tag;
  document.getElementById("ed-list-desc").value = list.description;

  renderEditorTickers();
  document.getElementById("editor-overlay").style.display = "block";
}

function closeEditor() {
  document.getElementById("editor-overlay").style.display = "none";
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
      <span style="color:#4a5568;font-family:monospace;font-size:10px;width:24px;">${i + 1}</span>
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

async function refreshApp() {
  try {
    const res = await fetch('/api/init');
    const data = await res.json();
    LISTS = data.lists;
    TAG_COLORS = data.tagColors;
    GLOBAL_BASE_CURRENCY = data.settings.GLOBAL_BASE_CURRENCY || "USD";

    // clear caches since data changed
    state.cache = {};
    state.fxCache = {};

    buildSidebar();

    if (state.activeList && LISTS[state.activeList]) {
      // re-activate the current list
      document.querySelectorAll(".list-btn").forEach(b => {
        b.classList.toggle("active", b.dataset.list === state.activeList);
      });
      const list = LISTS[state.activeList];
      document.getElementById("page-title").textContent = list.name;
      document.getElementById("header-tag").textContent = list.tag;
      document.getElementById("page-subtitle").textContent = list.description;
      loadData(state.activeList);
    } else {
      const firstId = Object.keys(LISTS)[0];
      if (firstId) switchList(firstId);
    }
  } catch (e) {
    console.error("Failed to refresh:", e);
  }
}

async function saveBaseCurrency() {
  const val = document.getElementById("ed-base-currency").value.toUpperCase().trim();
  if (!val || val.length !== 3) return alert("Currency must be a 3-letter ISO code.");
  try {
    await fetch("/api/settings/GLOBAL_BASE_CURRENCY", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: val })
    });
    GLOBAL_BASE_CURRENCY = val;
    state.cache = {};
    state.fxCache = {};
    closeEditor();
    if (state.activeList) loadData(state.activeList);
  } catch (e) { alert("Error saving currency: " + e.message); }
}

async function saveListMeta() {
  const slug = state.activeList;
  const body = {
    name: document.getElementById("ed-list-name").value,
    short_name: document.getElementById("ed-list-short").value,
    category: document.getElementById("ed-list-category").value,
    tag: document.getElementById("ed-list-tag").value,
    description: document.getElementById("ed-list-desc").value,
  };
  try {
    await fetch(`/api/lists/${slug}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    await refreshApp();
    openEditor(); // re-open to show updated values
  } catch (e) { alert("Error saving list: " + e.message); }
}

async function deleteList() {
  const slug = state.activeList;
  if (!confirm(`Delete the entire "${LISTS[slug].name}" list?`)) return;
  try {
    await fetch(`/api/lists/${slug}`, { method: "DELETE" });
    state.activeList = null;
    await refreshApp();
    closeEditor();
  } catch (e) { alert("Error deleting list: " + e.message); }
}

async function createList() {
  const slug = document.getElementById("ed-new-slug").value.trim();
  const name = document.getElementById("ed-new-name").value.trim();
  const short_name = document.getElementById("ed-new-short").value.trim();
  const category = document.getElementById("ed-new-category").value.trim() || "Other";
  if (!slug || !name || !short_name) return alert("Slug, Name, and Short Name are required.");
  try {
    await fetch("/api/lists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug, name, short_name, category, description: "", tag: "", currency: GLOBAL_BASE_CURRENCY })
    });
    document.getElementById("ed-new-slug").value = "";
    document.getElementById("ed-new-name").value = "";
    document.getElementById("ed-new-short").value = "";
    document.getElementById("ed-new-category").value = "";
    await refreshApp();
    switchList(slug);
    openEditor();
  } catch (e) { alert("Error creating list: " + e.message); }
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
    // flash green on the save button
    btn.style.borderColor = "#38a169";
    btn.textContent = "✓";
    setTimeout(() => { btn.style.borderColor = "#68d391"; btn.textContent = "Save"; }, 800);

    // update local state too
    const list = LISTS[state.activeList];
    const item = list.items.find(t => t.id === id);
    if (item) {
      if (body.symbol) item.ticker = body.symbol;
      if (body.name) item.name = body.name;
      if (body.tag) item.tag = body.tag;
      if (body.currency) item.currency = body.currency;
    }
    // clear the cache so data refreshes
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
    document.querySelectorAll(".list-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.list === state.activeList);
    });
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
    document.querySelectorAll(".list-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.list === state.activeList);
    });
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
    const firstListId = Object.keys(LISTS)[0];
    switchList(firstListId);
  } catch (e) {
    document.getElementById("status-text").textContent = "Error loading data from server";
    document.getElementById("status-bar").className = "s-err";
    console.error(e);
  }
}

initApp();