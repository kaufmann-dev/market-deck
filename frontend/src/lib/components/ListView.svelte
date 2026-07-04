<script lang="ts">
  import { ArrowLeft, Pencil } from "@lucide/svelte";
  import Controls from "./Controls.svelte";
  import HeatmapTable from "./HeatmapTable.svelte";
  import HighlightBanner from "./HighlightBanner.svelte";
  import RankingsTable from "./RankingsTable.svelte";
  import StatusBar from "./StatusBar.svelte";
  import TickerEditor from "./modals/TickerEditor.svelte";
  import { rankRows } from "../scoring";
  import { app } from "../stores/app.svelte";
  import { auth } from "../stores/auth.svelte";

  let editorOpen = $state(false);

  const list = $derived(app.active);
  const metrics = $derived(app.activeMetrics());
  const loadState = $derived(app.activeLoadState());
  const rows = $derived(metrics ? rankRows(metrics, app.lb, app.tagFilter) : []);

  const methodNote = $derived.by(() => {
    const today = new Date();
    const target = new Date(today.getFullYear(), today.getMonth() - app.lb, today.getDate());
    const dateStr = target.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    return `${app.lb}M return · Since ${dateStr} · Base ${app.baseCurrency}`;
  });
</script>

<div class="view-list">
  <div class="list-topbar">
    <button class="breadcrumb-btn" onclick={() => app.showHome()}>
      <ArrowLeft class="icon" aria-hidden="true" /> Home
    </button>
    <span class="updated-label">
      {app.activeUpdatedAt() ? `Updated: ${app.activeUpdatedAt()}` : ""}
    </span>
    {#if auth.isAdmin}
      <button onclick={() => (editorOpen = true)} class="edit-tickers-btn">
        <Pencil class="icon" aria-hidden="true" /> Edit Tickers
      </button>
    {/if}
  </div>
  <h1 class="list-title">{list?.name ?? ""}</h1>
  <p class="subtitle">{list?.description ?? ""}</p>

  <StatusBar />

  {#if loadState?.status === "ok" && metrics && list}
    <div class="app-content">
      <Controls {list} />
      <HighlightBanner {rows} />

      {#if app.viewTab === "r"}
        <div class="method-note">{methodNote}</div>
        <RankingsTable {rows} {list} />
      {:else}
        <div class="method-note">Monthly return history</div>
        <HeatmapTable {rows} />
      {/if}

      <div class="footer">
        Source: Yahoo Finance daily adjusted close · Returns = (today's adj. close) / (adj. close
        on or just after the same date N months ago) − 1 · Not financial advice
      </div>
    </div>
  {/if}
</div>

{#if editorOpen && app.activeList}
  <TickerEditor slug={app.activeList} onClose={() => (editorOpen = false)} />
{/if}
