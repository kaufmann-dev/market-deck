import { apiJson, del, putJson } from "../api/client";
import type { InitResponse, ListInfo, MetricsResponse, TagInfo } from "../api/types";
import { auth } from "./auth.svelte";

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
  lb = $state(3);
  topN = $state(3);
  viewTab = $state<"r" | "h">("r");
  tagFilter = $state("All");

  metrics = $state<Record<string, MetricsResponse>>({});
  loadState = $state<Record<string, LoadState>>({});
  updatedAt = $state<Record<string, string>>({});

  #pending = new Map<string, Promise<void>>();
  #controllers = new Map<string, AbortController>();

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

  async loadInit(): Promise<void> {
    const data = await apiJson<InitResponse>("/api/init");
    for (const list of Object.values(data.lists)) {
      list.tags = (list.tags ?? []).filter((tag) => normalizeTag(tag.tag));
      list.items = (list.items ?? []).map((item) => ({ ...item, tag: normalizeTag(item.tag) }));
    }
    this.lists = data.lists;
    this.settings = data.settings;
  }

  showHome(): void {
    this.currentView = "home";
    this.activeList = null;
  }

  openList(slug: string): void {
    this.currentView = "list";
    this.activeList = slug;
    this.tagFilter = "All";
    this.viewTab = "r";
    void this.loadMetrics(slug);
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

  /** Reload lists/settings after a mutation and refresh the active list's metrics. */
  async refresh({ invalidate = true }: { invalidate?: boolean } = {}): Promise<void> {
    await this.loadInit();
    if (invalidate) this.invalidateMetrics();
    if (this.currentView === "list" && this.activeList) {
      if (!this.lists[this.activeList]) {
        this.showHome();
        return;
      }
      void this.loadMetrics(this.activeList, { force: true });
    }
  }

  async setBaseCurrency(value: string): Promise<void> {
    if (auth.isDemo) {
      this.demoBaseCurrency = value;
      this.invalidateMetrics();
      if (this.currentView === "list" && this.activeList) {
        void this.loadMetrics(this.activeList);
      }
      return;
    }
    await putJson("/api/settings/GLOBAL_BASE_CURRENCY", { value });
    // Clear the server price cache so FX series for the new base are fetched immediately.
    await del("/api/prices/cache");
    this.settings = { ...this.settings, GLOBAL_BASE_CURRENCY: value };
    this.invalidateMetrics();
    if (this.currentView === "list" && this.activeList) {
      void this.loadMetrics(this.activeList);
    }
  }

  reset(): void {
    this.lists = {};
    this.settings = {};
    this.demoBaseCurrency = null;
    this.currentView = "home";
    this.activeList = null;
    this.tagFilter = "All";
    this.invalidateMetrics();
    this.loadState = {};
    this.updatedAt = {};
  }
}

export const app = new AppStore();
