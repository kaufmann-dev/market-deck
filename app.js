let LISTS = {};
let TAG_COLORS = {};


// ═══════════════════════════════════════════
//  PROXY CONFIG & STATE
// ═══════════════════════════════════════════
const PROXIES = [
  u => `https://corsproxy.io/?${encodeURIComponent(u)}`,
  u => `https://api.allorigins.win/get?url=${encodeURIComponent(u)}`,
  u => `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(u)}`,
];

const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

let state = {
  activeList: null,
  lb: 3,
  topN: 3,
  view: "r",
  cache: {},       // { listId: { ticker: [points] } }
  fxCache: {},     // { "EURUSD=X": [points], etc }
  workingProxy: null,
};

const GLOBAL_BASE_CURRENCY = "USD";

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

// ═══════════════════════════════════════════
//  FETCH
// ═══════════════════════════════════════════
async function fetchWithFallback(url) {
  const proxies = state.workingProxy !== null
    ? [PROXIES[state.workingProxy], ...PROXIES.filter((_, i) => i !== state.workingProxy)]
    : PROXIES;
  for (const proxyFn of proxies) {
    const idx = PROXIES.indexOf(proxyFn);
    try {
      const res = await fetch(proxyFn(url), { signal: AbortSignal.timeout(9000) });
      if (!res.ok) continue;
      const raw = await res.text();
      let parsed;
      try {
        const j = JSON.parse(raw);
        parsed = j.contents ? JSON.parse(j.contents) : j;
      } catch { continue; }
      if (!parsed?.chart?.result?.[0]) continue;
      state.workingProxy = idx;
      return parsed;
    } catch { /* try next */ }
  }
  throw new Error("All proxies failed — Yahoo Finance data unavailable.");
}

async function fetchTicker(ticker) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?interval=1d&range=14mo&includePrePost=false`;
  const data = await fetchWithFallback(url);
  const r = data.chart.result[0];
  const closes = r.indicators.adjclose[0].adjclose;
  const ts = r.timestamp;
  return ts.map((t, i) => ({ date: new Date(t * 1000), close: closes[i] }))
    .filter(p => p.close !== null && p.close !== undefined && !isNaN(p.close));
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
//  LOAD DATA
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
    // 1. Identify all foreign currencies in this list
    const foreignCurrencies = [...new Set(
      list.items
        .map(s => s.currency)
        .filter(c => c && c !== GLOBAL_BASE_CURRENCY)
    )];

    let loaded = 0;
    const total = list.items.length + foreignCurrencies.length;

    // 2. Fetch Forex pairs alongside standard tickers
    const fetchPromises = [];

    // Forex fetch promises
    foreignCurrencies.forEach(cur => {
      // e.g. "EURUSD=X"
      // If the currency is "USX" (US Cents), we handle it mathematically later, no need to fetch it
      if (cur === "USX") {
        loaded++;
        return;
      }

      let fxTicker = `${cur}${GLOBAL_BASE_CURRENCY}=X`;
      if (cur === "GBp") {
        fxTicker = `GBP${GLOBAL_BASE_CURRENCY}=X`;
      }
      // Check if we already have it in the global fxCache
      if (!state.fxCache[fxTicker]) {
        fetchPromises.push(
          fetchTicker(fxTicker).then(data => {
            state.fxCache[fxTicker] = data;
            loaded++;
            if (state.activeList === listId) {
              document.getElementById("status-text").textContent = `Loading Forex rates… ${loaded}/${total}`;
            }
          }).catch(() => {
            state.fxCache[fxTicker] = null;
            loaded++;
          })
        );
      } else {
        loaded++;
      }
    });

    // Stock fetch promises
    list.items.forEach(s => {
      fetchPromises.push(
        fetchTicker(s.ticker).then(data => {
          state.cache[listId][s.ticker] = data;
          loaded++;
          if (state.activeList === listId) {
            document.getElementById("status-text").textContent = `Loading ${list.shortName}… ${loaded}/${total} tickers`;
          }
        }).catch(() => {
          state.cache[listId][s.ticker] = null;
          loaded++;
        })
      );
    });

    await Promise.all(fetchPromises);
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
//  INIT
// ═══════════════════════════════════════════
async function initApp() {
  try {
    const [resLists, resColors] = await Promise.all([
      fetch('lists.json'),
      fetch('colors.json')
    ]);
    LISTS = await resLists.json();
    TAG_COLORS = await resColors.json();

    buildSidebar();
    const firstListId = Object.keys(LISTS)[0];
    switchList(firstListId);
  } catch (e) {
    document.getElementById("status-text").textContent = "Error loading lists.json or colors.json";
    document.getElementById("status-bar").className = "s-err";
    console.error(e);
  }
}

initApp();