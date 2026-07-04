import { apiJson, del, putJson } from "../api/client";
import type {
  ChartResponse,
  FinancialsResponse,
  InitResponse,
  ListInfo,
  MetricsResponse,
  NewsItem,
  StockOverview,
  TagInfo,
} from "../api/types";
import { auth } from "./auth.svelte";
import type { Route } from "./router.svelte";
import { router } from "./router.svelte";

export function normalizeCategory(category: string | null | undefined): string {
  const cleaned = String(category ?? "").trim().replace(/\s+/g, " ");
  return (cleaned || "Other").toUpperCase();
}

export function normalizeTag(tag: string | null | undefined): string {
  return String(tag ?? "").trim().replace(/\s+/g, " ").toUpperCase();
}

export function sortedTags(list: ListInfo | null | undefined): TagInfo[] {
  return [...(list?.tags ?? [])]
    .filter((tag) => normalizeTag(tag.tag))
    .sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0) || a.tag.localeCompare(b.tag));
}

interface LoadState {
  status: "loading" | "ok" | "error";
  message?: string;
}

class AppStore {
  lists = $state<Record<string, ListInfo>>({});
  settings = $state<Record<string, string>>({});
  /** Demo sessions change the base currency locally only. */
  demoBaseCurrency = $state<string | null>(null);

  currentView = $state<"home" | "list">("home");
  activeList = $state<string | null>(null);
  activeStock = $state<string | null>(null);
  lb = $state(3);
  topN = $state(3);
  viewTab = $state<"r" | "h">("r");
  tagFilter = $state("All");

  metrics = $state<Record<string, MetricsResponse>>({});
  loadState = $state<Record<string, LoadState>>({});
  updatedAt = $state<Record<string, string>>({});
  stockOverview = $state<Record<string, StockOverview>>({});
  stockChart = $state<Record<string, ChartResponse>>({});
  stockNews = $state<Record<string, NewsItem[]>>({});
  stockFinancials = $state<Record<string, FinancialsResponse>>({});
  stockLoadState = $state<Record<string, LoadState>>({});
  stockUpdatedAt = $state<Record<string, string>>({});

  #pending = new Map<string, Promise<void>>();
  #controllers = new Map<string, AbortController>();
  #stockPending = new Map<string, Promise<void>>();
  #stockControllers = new Map<string, AbortController>();

  get baseCurrency(): string {
    if (auth.isDemo && this.demoBaseCurrency) return this.demoBaseCurrency;
    return this.settings.GLOBAL_BASE_CURRENCY || "EUR";
  }

  get active(): ListInfo | null {
    return this.activeList ? (this.lists[this.activeList] ?? null) : null;
  }

  #metricsKey(slug: string): string {
    return `${slug}|${this.baseCurrency}`;
  }

  #symbolKey(symbol: string): string {
    return String(symbol ?? "").trim().toUpperCase();
  }

  #stockKey(kind: string, symbol: string, suffix = ""): string {
    return `${kind}:${this.#symbolKey(symbol)}${suffix ? `:${suffix}` : ""}`;
  }

  #chartKey(symbol: string, range: string, interval = "1d"): string {
    return this.#stockKey("chart", symbol, `${range}:${interval}`);
  }

  activeMetrics(): MetricsResponse | null {
    if (!this.activeList) return null;
    return this.metrics[this.#metricsKey(this.activeList)] ?? null;
  }

  activeLoadState(): LoadState | null {
    if (!this.activeList) return null;
    return this.loadState[this.#metricsKey(this.activeList)] ?? null;
  }

  activeUpdatedAt(): string {
    if (!this.activeList) return "";
    return this.updatedAt[this.#metricsKey(this.activeList)] ?? "";
  }

  stockOverviewState(symbol: string): LoadState | null {
    return this.stockLoadState[this.#stockKey("overview", symbol)] ?? null;
  }

  stockChartState(symbol: string, range: string, interval = "1d"): LoadState | null {
    return this.stockLoadState[this.#chartKey(symbol, range, interval)] ?? null;
  }

  stockNewsState(symbol: string): LoadState | null {
    return this.stockLoadState[this.#stockKey("news", symbol)] ?? null;
  }

  stockFinancialsState(symbol: string): LoadState | null {
    return this.stockLoadState[this.#stockKey("financials", symbol)] ?? null;
  }

  chartFor(symbol: string, range = "1y", interval = "1d"): ChartResponse | null {
    return this.stockChart[this.#chartKey(symbol, range, interval)] ?? null;
  }

  chartUpdatedAt(symbol: string, range = "1y", interval = "1d"): string {
    return this.stockUpdatedAt[this.#chartKey(symbol, range, interval)] ?? "";
  }

  async loadInit(): Promise<void> {
    const data = await apiJson<InitResponse>("/api/init");
    for (const list of Object.values(data.lists)) {
      list.tags = (list.tags ?? []).filter((tag) => normalizeTag(tag.tag));
      list.items = (list.items ?? []).map((item) => ({ ...item, tag: normalizeTag(item.tag) }));
    }
    this.lists = data.lists;
    this.settings = data.settings;
  }

  activateHome(): void {
    this.currentView = "home";
    this.activeList = null;
    this.activeStock = null;
  }

  activateList(slug: string): void {
    this.currentView = "list";
    this.activeList = slug;
    this.activeStock = null;
    this.tagFilter = "All";
    this.viewTab = "r";
  }

  activateStock(symbol: string): void {
    this.currentView = "home";
    this.activeList = null;
    this.activeStock = this.#symbolKey(symbol);
  }

  syncRoute(route: Route): void {
    if (route.name === "list") {
      this.activateList(route.params.slug);
      void this.loadMetrics(route.params.slug);
      return;
    }
    if (route.name === "stock") {
      this.activateStock(route.params.symbol);
      void this.loadStock(route.params.symbol);
      return;
    }
    this.activateHome();
  }

  showHome(): void {
    router.navigate("/");
  }

  openList(slug: string): void {
    router.navigate(`/list/${encodeURIComponent(slug)}`);
  }

  openStock(symbol: string): void {
    router.navigate(`/stock/${encodeURIComponent(this.#symbolKey(symbol))}`);
  }

  async loadStock(symbol: string, { force = false } = {}): Promise<void> {
    const normalized = this.#symbolKey(symbol);
    await this.loadStockOverview(normalized, { force });
    void this.loadStockChart(normalized, "1y", { force });
    void this.loadStockNews(normalized, { force });
  }

  async loadStockOverview(symbol: string, { force = false } = {}): Promise<void> {
    const normalized = this.#symbolKey(symbol);
    const key = this.#stockKey("overview", normalized);
    if (!force && this.stockOverview[normalized]) return;

    const pending = this.#stockPending.get(key);
    if (pending) return pending;

    const controller = new AbortController();
    this.#stockControllers.set(key, controller);
    this.stockLoadState = { ...this.stockLoadState, [key]: { status: "loading" } };

    const load = (async () => {
      try {
        const data = await apiJson<StockOverview>(
          `/api/stocks/${encodeURIComponent(normalized)}`,
          { signal: controller.signal },
        );
        this.stockOverview = { ...this.stockOverview, [normalized]: data };
        this.stockUpdatedAt = { ...this.stockUpdatedAt, [key]: new Date().toLocaleTimeString() };
        this.stockLoadState = { ...this.stockLoadState, [key]: { status: "ok" } };
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        this.stockLoadState = {
          ...this.stockLoadState,
          [key]: { status: "error", message: error instanceof Error ? error.message : String(error) },
        };
      } finally {
        this.#stockPending.delete(key);
        this.#stockControllers.delete(key);
      }
    })();
    this.#stockPending.set(key, load);
    return load;
  }

  async loadStockChart(
    symbol: string,
    range = "1y",
    { interval = "1d", force = false }: { interval?: string; force?: boolean } = {},
  ): Promise<void> {
    const normalized = this.#symbolKey(symbol);
    const key = this.#chartKey(normalized, range, interval);
    if (!force && this.stockChart[key]) return;

    const pending = this.#stockPending.get(key);
    if (pending) return pending;

    const controller = new AbortController();
    this.#stockControllers.set(key, controller);
    this.stockLoadState = { ...this.stockLoadState, [key]: { status: "loading" } };

    const load = (async () => {
      try {
        const data = await apiJson<ChartResponse>(
          `/api/stocks/${encodeURIComponent(normalized)}/chart?range=${encodeURIComponent(range)}&interval=${encodeURIComponent(interval)}`,
          { signal: controller.signal },
        );
        this.stockChart = { ...this.stockChart, [key]: data };
        this.stockUpdatedAt = { ...this.stockUpdatedAt, [key]: new Date().toLocaleTimeString() };
        this.stockLoadState = { ...this.stockLoadState, [key]: { status: "ok" } };
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        this.stockLoadState = {
          ...this.stockLoadState,
          [key]: { status: "error", message: error instanceof Error ? error.message : String(error) },
        };
      } finally {
        this.#stockPending.delete(key);
        this.#stockControllers.delete(key);
      }
    })();
    this.#stockPending.set(key, load);
    return load;
  }

  async loadStockNews(symbol: string, { force = false } = {}): Promise<void> {
    const normalized = this.#symbolKey(symbol);
    const key = this.#stockKey("news", normalized);
    if (!force && this.stockNews[normalized]) return;

    const pending = this.#stockPending.get(key);
    if (pending) return pending;

    const controller = new AbortController();
    this.#stockControllers.set(key, controller);
    this.stockLoadState = { ...this.stockLoadState, [key]: { status: "loading" } };

    const load = (async () => {
      try {
        const data = await apiJson<{ news: NewsItem[] }>(
          `/api/stocks/${encodeURIComponent(normalized)}/news`,
          { signal: controller.signal },
        );
        this.stockNews = { ...this.stockNews, [normalized]: data.news };
        this.stockUpdatedAt = { ...this.stockUpdatedAt, [key]: new Date().toLocaleTimeString() };
        this.stockLoadState = { ...this.stockLoadState, [key]: { status: "ok" } };
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        this.stockLoadState = {
          ...this.stockLoadState,
          [key]: { status: "error", message: error instanceof Error ? error.message : String(error) },
        };
      } finally {
        this.#stockPending.delete(key);
        this.#stockControllers.delete(key);
      }
    })();
    this.#stockPending.set(key, load);
    return load;
  }

  async loadStockFinancials(symbol: string, { force = false } = {}): Promise<void> {
    const normalized = this.#symbolKey(symbol);
    const key = this.#stockKey("financials", normalized);
    if (!force && this.stockFinancials[normalized]) return;

    const pending = this.#stockPending.get(key);
    if (pending) return pending;

    const controller = new AbortController();
    this.#stockControllers.set(key, controller);
    this.stockLoadState = { ...this.stockLoadState, [key]: { status: "loading" } };

    const load = (async () => {
      try {
        const data = await apiJson<FinancialsResponse>(
          `/api/stocks/${encodeURIComponent(normalized)}/financials`,
          { signal: controller.signal },
        );
        this.stockFinancials = { ...this.stockFinancials, [normalized]: data };
        this.stockUpdatedAt = { ...this.stockUpdatedAt, [key]: new Date().toLocaleTimeString() };
        this.stockLoadState = { ...this.stockLoadState, [key]: { status: "ok" } };
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        this.stockLoadState = {
          ...this.stockLoadState,
          [key]: { status: "error", message: error instanceof Error ? error.message : String(error) },
        };
      } finally {
        this.#stockPending.delete(key);
        this.#stockControllers.delete(key);
      }
    })();
    this.#stockPending.set(key, load);
    return load;
  }

  async loadMetrics(slug: string, { force = false } = {}): Promise<void> {
    const key = this.#metricsKey(slug);
    if (!force && this.metrics[key]) return;

    const pending = this.#pending.get(key);
    if (pending) return pending;

    const controller = new AbortController();
    this.#controllers.set(key, controller);
    this.loadState = { ...this.loadState, [key]: { status: "loading" } };

    const query = auth.isDemo && this.demoBaseCurrency
      ? `?base=${encodeURIComponent(this.demoBaseCurrency)}`
      : "";
    const load = (async () => {
      try {
        const data = await apiJson<MetricsResponse>(
          `/api/lists/${encodeURIComponent(slug)}/metrics${query}`,
          { signal: controller.signal },
        );
        this.metrics = { ...this.metrics, [key]: data };
        this.updatedAt = { ...this.updatedAt, [key]: new Date().toLocaleTimeString() };
        this.loadState = { ...this.loadState, [key]: { status: "ok" } };
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        this.loadState = {
          ...this.loadState,
          [key]: { status: "error", message: error instanceof Error ? error.message : String(error) },
        };
      } finally {
        this.#pending.delete(key);
        this.#controllers.delete(key);
      }
    })();
    this.#pending.set(key, load);
    return load;
  }

  invalidateMetrics(slug?: string): void {
    for (const controller of this.#controllers.values()) controller.abort();
    this.#pending.clear();
    this.#controllers.clear();
    if (slug) {
      this.metrics = Object.fromEntries(
        Object.entries(this.metrics).filter(([key]) => !key.startsWith(`${slug}|`)),
      );
    } else {
      this.metrics = {};
    }
  }

  invalidateStock(symbol?: string): void {
    for (const controller of this.#stockControllers.values()) controller.abort();
    this.#stockPending.clear();
    this.#stockControllers.clear();
    if (!symbol) {
      this.stockOverview = {};
      this.stockChart = {};
      this.stockNews = {};
      this.stockFinancials = {};
      this.stockLoadState = {};
      this.stockUpdatedAt = {};
      return;
    }

    const normalized = this.#symbolKey(symbol);
    this.stockOverview = Object.fromEntries(
      Object.entries(this.stockOverview).filter(([key]) => key !== normalized),
    );
    this.stockNews = Object.fromEntries(
      Object.entries(this.stockNews).filter(([key]) => key !== normalized),
    );
    this.stockFinancials = Object.fromEntries(
      Object.entries(this.stockFinancials).filter(([key]) => key !== normalized),
    );
    this.stockChart = Object.fromEntries(
      Object.entries(this.stockChart).filter(([key]) => !key.startsWith(`chart:${normalized}:`)),
    );
    this.stockLoadState = Object.fromEntries(
      Object.entries(this.stockLoadState).filter(([key]) => !key.includes(`:${normalized}`)),
    );
    this.stockUpdatedAt = Object.fromEntries(
      Object.entries(this.stockUpdatedAt).filter(([key]) => !key.includes(`:${normalized}`)),
    );
  }

  /** Reload lists/settings after a mutation and refresh the active list's metrics. */
  async refresh({ invalidate = true }: { invalidate?: boolean } = {}): Promise<void> {
    await this.loadInit();
    if (invalidate) this.invalidateMetrics();
    if (router.route.name === "list" && this.activeList) {
      if (!this.lists[this.activeList]) {
        this.showHome();
        return;
      }
      void this.loadMetrics(this.activeList, { force: true });
    } else if (router.route.name === "stock" && this.activeStock) {
      void this.loadStock(this.activeStock, { force: false });
    }
  }

  async setBaseCurrency(value: string): Promise<void> {
    if (auth.isDemo) {
      this.demoBaseCurrency = value;
      this.invalidateMetrics();
      if (router.route.name === "list" && this.activeList) {
        void this.loadMetrics(this.activeList);
      }
      return;
    }
    await putJson("/api/settings/GLOBAL_BASE_CURRENCY", { value });
    // Clear the server price cache so FX series for the new base are fetched immediately.
    await del("/api/prices/cache");
    this.settings = { ...this.settings, GLOBAL_BASE_CURRENCY: value };
    this.invalidateMetrics();
    if (router.route.name === "list" && this.activeList) {
      void this.loadMetrics(this.activeList);
    }
  }

  reset(): void {
    this.lists = {};
    this.settings = {};
    this.demoBaseCurrency = null;
    this.currentView = "home";
    this.activeList = null;
    this.activeStock = null;
    this.tagFilter = "All";
    this.invalidateMetrics();
    this.invalidateStock();
    this.loadState = {};
    this.updatedAt = {};
  }
}

export const app = new AppStore();
