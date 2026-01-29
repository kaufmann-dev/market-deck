import {
    LISTS, TAG_COLORS, GLOBAL_BASE_CURRENCY, state,
    setLists, setTagColors, setGlobalBaseCurrency, _editingListSlug
} from './state.js';
import { autoGenerateTagColors, parsePoints } from './utils.js';
import { renderTagColorsEditor, closeListEditModal, buildSidebar, renderHomepage, showHome, renderEditorTickers, finishLoad } from './ui.js';

export async function updateTagColor(tag, hex) {
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

export async function deleteTagColor(tag) {
    if (!confirm(`Remove color for "${tag}"?`)) return;
    try {
        await fetch(`/api/tag-colors/${encodeURIComponent(tag)}`, { method: "DELETE" });
        delete TAG_COLORS[tag];
        renderTagColorsEditor();
    } catch (e) { alert("Error: " + e.message); }
}

export async function addTagColor() {
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

export async function saveListFromModal() {
    const name = document.getElementById("le-name").value.trim();
    const short_name = document.getElementById("le-short").value.trim();
    const category = document.getElementById("le-category").value.trim() || "Other";
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
                body: JSON.stringify({ slug, name, short_name, category, description, tag: "", currency: GLOBAL_BASE_CURRENCY })
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
                body: JSON.stringify({ name, short_name, category, description, tag: LISTS[_editingListSlug]?.tag || "" })
            });
            closeListEditModal();
            await refreshApp();
        } catch (e) { alert("Error: " + e.message); }
    }
}

export async function deleteListFromModal() {
    if (!_editingListSlug || _editingListSlug === "__new__") return;
    if (!confirm(`Delete the entire "${LISTS[_editingListSlug].name}" list?`)) return;
    try {
        await fetch(`/api/lists/${_editingListSlug}`, { method: "DELETE" });
        closeListEditModal();
        await refreshApp();
    } catch (e) { alert("Error: " + e.message); }
}

export async function loadData(listId) {
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
        const stockTickers = list.items.map(s => s.ticker);
        const foreignCurrencies = [...new Set(
            list.items.map(s => s.currency).filter(c => c && c !== GLOBAL_BASE_CURRENCY && c !== "USX")
        )];

        const fxTickers = foreignCurrencies.map(cur => {
            const prefix = cur === "GBp" ? "GBP" : cur;
            return `${prefix}${GLOBAL_BASE_CURRENCY}=X`;
        }).filter(t => !state.fxCache[t]); // skip already cached FX

        const allTickers = [...stockTickers, ...fxTickers];

        if (state.activeList === listId) {
            document.getElementById("status-text").textContent = `Fetching ${stockTickers.length} tickers + ${fxTickers.length} FX rates…`;
        }

        const res = await fetch("/api/prices", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tickers: allTickers })
        });
        const priceData = await res.json();

        stockTickers.forEach(t => { state.cache[listId][t] = parsePoints(priceData[t]); });
        fxTickers.forEach(t => { state.fxCache[t] = parsePoints(priceData[t]); });

        if (state.activeList === listId) finishLoad(listId);
    } catch (e) {
        if (state.activeList === listId) {
            sb.className = "s-err";
            sb.querySelector(".spinner").style.display = "none";
            document.getElementById("status-text").innerHTML =
                "⚠ " + e.message + ` <button class="retry-btn" onclick="retryLoadData('${listId}')">↻ Retry</button>`;
        }
    }
}

export function retryLoadData(listId) {
    delete state.cache[listId];
    loadData(listId);
}

export async function saveBaseCurrency() {
    const input = document.getElementById("home-currency-input");
    const val = input.value.toUpperCase().trim();
    if (!val || val.length !== 3) return alert("Currency must be a 3-letter ISO code.");
    try {
        await fetch("/api/settings/GLOBAL_BASE_CURRENCY", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ value: val })
        });
        setGlobalBaseCurrency(val);
        state.cache = {};
        state.fxCache = {};
    } catch (e) { alert("Error saving currency: " + e.message); }
}

export async function refreshApp() {
    try {
        const res = await fetch('/api/init');
        const data = await res.json();
        setLists(data.lists);
        setTagColors(data.tagColors);
        setGlobalBaseCurrency(data.settings.GLOBAL_BASE_CURRENCY || "USD");

        state.cache = {};
        state.fxCache = {};

        buildSidebar();

        if (state.currentView === "home") {
            renderHomepage();
        } else if (state.activeList && LISTS[state.activeList]) {
            const list = LISTS[state.activeList];
            document.getElementById("page-title").textContent = list.name;
            document.getElementById("page-subtitle").textContent = list.description;
            loadData(state.activeList);
        } else {
            showHome();
        }
    } catch (e) {
        console.error("Failed to refresh:", e);
    }
}

export async function saveTicker(id, btn) {
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

export async function deleteTicker(id) {
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

export async function addTicker() {
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

export async function initApp() {
    try {
        const res = await fetch('/api/init');
        const data = await res.json();

        setLists(data.lists);
        setTagColors(data.tagColors);
        setGlobalBaseCurrency(data.settings.GLOBAL_BASE_CURRENCY || "USD");

        buildSidebar();
        showHome();
    } catch (e) {
        document.getElementById("view-home").style.display = "block";
        document.getElementById("home-grid").innerHTML = `<div style="color:#fc8181;font-family:monospace;padding:20px;">Error loading data from server</div>`;
        console.error(e);
    }
}
