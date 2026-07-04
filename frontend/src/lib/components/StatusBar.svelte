<script lang="ts">
  import { app } from "../stores/app.svelte";

  const list = $derived(app.active);
  const metrics = $derived(app.activeMetrics());
  const loadState = $derived(app.activeLoadState());

  const barClass = $derived.by(() => {
    if (!loadState || loadState.status === "loading") return "s-load";
    if (loadState.status === "error") return "s-err";
    return metrics && metrics.failed.length > 0 ? "s-load" : "s-ok";
  });

  const statusText = $derived.by(() => {
    if (!loadState || loadState.status === "loading") {
      return `Loading price data for ${list?.shortName ?? ""}…`;
    }
    if (loadState.status === "error") {
      return `⚠ ${loadState.message ?? "Failed to load"}`;
    }
    if (!metrics || !list) return "";
    const total = list.items.length;
    const failed = metrics.failed;
    let message = `${total - failed.length}/${total} tickers loaded`;
    if (failed.length > 0) {
      message += ` · ${failed.length} failed: ${failed.join(", ")}`;
    }
    return message;
  });

  function retry() {
    if (app.activeList) void app.loadMetrics(app.activeList, { force: true });
  }
</script>

<div class="status-bar {barClass}">
  <div class="spinner" style:display={loadState?.status === "loading" ? "block" : "none"}></div>
  <span class="status-text">
    {statusText}
    {#if loadState?.status === "error"}
      <button class="retry-btn" onclick={retry}>↻ Retry</button>
    {/if}
  </span>
</div>
