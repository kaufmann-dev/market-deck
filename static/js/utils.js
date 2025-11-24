import { TAG_COLORS, MONTH_LABELS } from './state.js';

export function fmtPct(v) {
    if (v === null || v === undefined) return "—";
    return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}
export function retTextColor(v) { return (!v && v !== 0) ? "#718096" : v >= 0 ? "#68d391" : "#fc8181"; }
export function retBgColor(v) {
    if (v === null || v === undefined) return "#4a5568";
    if (v > 4) return "#38a169";
    if (v > 2) return "#68d391";
    if (v > 0) return "#9ae6b4";
    if (v > -2) return "#fc8181";
    if (v > -4) return "#e53e3e";
    return "#9b2c2c";
}

export function currencySymbol(c) {
    const formatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: c, minimumFractionDigits: 0, maximumFractionDigits: 0 });
    return formatter.format(0).replace(/\d/g, '').trim();
}

export function getTagStyle(tag) {
    const c = TAG_COLORS[tag] || TAG_COLORS["Other"] || { bg: "transparent", text: "#a0aec0", border: "transparent" };
    return `background:${c.bg};color:${c.text};border:1px solid ${c.border}`;
}

export function setStatus(html, type) {
    const bar = document.getElementById("status-bar");
    const txt = document.getElementById("status-text");
    bar.className = "s-" + type;
    bar.querySelector(".spinner").style.display = type === "load" ? "block" : "none";
    txt.innerHTML = html;
}

export function parsePoints(arr) {
    if (!arr) return null;
    return arr.map(p => ({ date: new Date(p.date), close: p.close }))
        .filter(p => p.close !== null && !isNaN(p.close));
}

export function closestAfter(points, targetDate) {
    for (let i = 0; i < points.length; i++) {
        if (points[i].date >= targetDate) return points[i];
    }
    return points[points.length - 1];
}

export function getMonthlyReturns(points) {
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

export function autoGenerateTagColors(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return {
        bg: `rgba(${r},${g},${b},0.12)`,
        text: hex,
        border: `rgba(${r},${g},${b},0.30)`
    };
}

export function hexFromTagColors(tc) {
    if (tc.text && tc.text.startsWith("#")) return tc.text;
    const m = tc.text && tc.text.match(/(\d+),\s*(\d+),\s*(\d+)/);
    if (m) {
        const toHex = n => parseInt(n).toString(16).padStart(2, "0");
        return `#${toHex(m[1])}${toHex(m[2])}${toHex(m[3])}`;
    }
    return "#68d391";
}
