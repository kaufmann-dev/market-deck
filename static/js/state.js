export const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export let LISTS = {};
export let TAG_COLORS = {};
export let GLOBAL_BASE_CURRENCY = "USD";

export let state = {
    activeList: null,
    lb: 3,
    topN: 3,
    view: "r",
    cache: {},
    fxCache: {},
    currentView: "home",
};

export function setLists(v) { LISTS = v; }
export function setTagColors(v) { TAG_COLORS = v; }
export function setGlobalBaseCurrency(v) { GLOBAL_BASE_CURRENCY = v; }

export let _editingListSlug = null;
export function setEditingListSlug(v) { _editingListSlug = v; }
