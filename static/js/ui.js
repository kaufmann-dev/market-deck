import {
    state, LISTS, TAG_COLORS, GLOBAL_BASE_CURRENCY,
    setEditingListSlug, _editingListSlug
} from './state.js';
import {
    autoGenerateTagColors, hexFromTagColors, fmtPct, retTextColor, retBgColor,
    currencySymbol, getTagStyle, closestAfter, getMonthlyReturns
} from './utils.js';
import { loadData } from './api.js';

export function buildSidebar() {
    const nav = document.getElementById("sidebar");
    let html = `<button class="sidebar-home-btn${state.currentView === 'home' ? ' active' : ''}" onclick="showHome()">⌂ MarketDeck</button>`;
    let lastCat = null;
    for (const [id, list] of Object.entries(LISTS)) {
        if (list.category !== lastCat) {
            html += `<div class="sidebar-section">${list.category}</div>`;
            lastCat = list.category;
        }
        html += `<button class="list-btn${state.activeList === id && state.currentView === 'list' ? ' active' : ''}" data-list="${id}" onclick="switchList('${id}')">
      <span>${list.shortName}</span>
      <span class="count">${list.items.length}</span>
    </button>`;
    }
    nav.innerHTML = html;
}

export function showHome() {
    state.currentView = "home";
    state.activeList = null;
    document.getElementById("view-home").style.display = "block";
    document.getElementById("view-list").style.display = "none";
    closeEditor();
    buildSidebar();
    renderHomepage();
}

export function switchList(id) {
    state.currentView = "list";
    state.activeList = id;

    document.getElementById("view-home").style.display = "none";
    document.getElementById("view-list").style.display = "block";

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

export function renderHomepage() {
    document.getElementById("home-currency-input").value = GLOBAL_BASE_CURRENCY;

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

    renderTagColorsEditor();
}

export function renderTagColorsEditor() {
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

export function openListEditModal(slug) {
    setEditingListSlug(slug);
    const list = LISTS[slug];
    document.getElementById("list-edit-title").textContent = `Edit: ${list.name}`;
    document.getElementById("le-name").value = list.name;
    document.getElementById("le-short").value = list.shortName;
    document.getElementById("le-category").value = list.category;
    document.getElementById("le-desc").value = list.description;
    document.querySelector("#list-edit-modal .btn-red").style.display = "";
    document.getElementById("list-edit-modal").style.display = "block";
}

export function closeListEditModal() {
    setEditingListSlug(null);
    document.getElementById("list-edit-modal").style.display = "none";
}

export function openCreateListModal() {
    setEditingListSlug("__new__");
    document.getElementById("list-edit-title").textContent = "Create New List";
    document.getElementById("le-name").value = "";
    document.getElementById("le-short").value = "";
    document.getElementById("le-category").value = "";
    document.getElementById("le-desc").value = "";
    document.querySelector("#list-edit-modal .btn-red").style.display = "none";
    document.getElementById("list-edit-modal").style.display = "block";
}

export function finishLoad(listId) {
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
        sb.className = "s-load";
    }
    document.getElementById("status-text").textContent = statusMsg;

    document.getElementById("app").style.display = "block";
    buildControls();
    render();
}

export function buildControls() {
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

export function setView(v) {
    state.view = v;
    document.getElementById("view-r").style.display = v === "r" ? "block" : "none";
    document.getElementById("view-h").style.display = v === "h" ? "block" : "none";
    document.getElementById("tab-r").className = v === "r" ? "a-purple" : "";
    document.getElementById("tab-h").className = v === "h" ? "a-purple" : "";
}

export function getScored() {
    const listId = state.activeList;
    const list = LISTS[listId];
    const cache = state.cache[listId] || {};
    const today = new Date();

    return list.items.map(s => {
        let pts = cache[s.ticker];
        if (!pts || pts.length < 2) return { ...s, score: null, currentPrice: null, basePrice: null, baseDate: null, monthly: [] };

        if (s.currency && s.currency !== GLOBAL_BASE_CURRENCY) {
            if (s.currency === "USX") {
                pts = pts.map(p => ({ date: p.date, close: p.close / 100 }));
            } else {
                let fxPrefix = s.currency;
                if (s.currency === "GBp") fxPrefix = "GBP";

                const fxTicker = `${fxPrefix}${GLOBAL_BASE_CURRENCY}=X`;
                const fxPts = state.fxCache[fxTicker];
                if (fxPts && fxPts.length > 0) {
                    pts = pts.map(p => {
                        let rate = null;
                        for (let i = fxPts.length - 1; i >= 0; i--) {
                            if (fxPts[i].date <= p.date) {
                                rate = fxPts[i].close;
                                break;
                            }
                        }
                        if (rate === null) rate = fxPts[0].close;

                        let finalRate = rate;
                        if (s.currency === "GBp") {
                            finalRate = rate / 100;
                        }

                        return { date: p.date, close: p.close * finalRate };
                    });
                }
            }
        }

        const currentPt = pts[pts.length - 1];

        const targetDate = new Date(today.getFullYear(), today.getMonth() - state.lb, today.getDate());
        const basePt = closestAfter(pts, targetDate);
        if (!basePt || basePt === currentPt) return { ...s, score: null, currentPrice: currentPt.close, basePrice: null, baseDate: null, monthly: [], ret12m: null };
        const score = +((currentPt.close / basePt.close - 1) * 100).toFixed(2);

        const targetDate12 = new Date(today.getFullYear(), today.getMonth() - 12, today.getDate());
        const basePt12 = closestAfter(pts, targetDate12);
        const ret12m = (basePt12 && basePt12 !== currentPt) ? +((currentPt.close / basePt12.close - 1) * 100).toFixed(2) : null;

        const monthly = getMonthlyReturns(pts);
        return { ...s, score, currentPrice: currentPt.close, basePrice: basePt.close, baseDate: basePt.date, monthly, ret12m };
    });
}

export function render() {
    if (!state.activeList) return;
    const list = LISTS[state.activeList];
    const sym = currencySymbol(GLOBAL_BASE_CURRENCY);
    const scored = getScored();
    const ranked = scored.filter(s => s.score !== null).sort((a, b) => b.score - a.score).map((s, i) => ({ ...s, rank: i + 1 }));
    const missing = scored.filter(s => s.score === null).map((s, i) => ({ ...s, rank: ranked.length + i + 1 }));
    const all = [...ranked, ...missing];
    const selected = ranked.filter(s => s.rank <= state.topN);

    const today = new Date();
    const targetDate = new Date(today.getFullYear(), today.getMonth() - state.lb, today.getDate());
    document.getElementById("method-note").textContent =
        "Return = (today's adj. close) ÷ (adj. close on " + targetDate.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) + ") − 1  ·  " + state.lb + "M momentum  ·  BASE CURRENCY: " + GLOBAL_BASE_CURRENCY;

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

export function openEditor() {
    if (!state.activeList) return;
    const slug = state.activeList;
    const list = LISTS[slug];
    document.getElementById("ed-list-name-label").textContent = list.name;
    renderEditorTickers();
    document.getElementById("editor-overlay").style.display = "block";
}

export function closeEditor() {
    document.getElementById("editor-overlay").style.display = "none";
}

export function renderEditorTickers() {
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
