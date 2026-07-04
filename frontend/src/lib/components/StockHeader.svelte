<script lang="ts">
  import { Plus } from "@lucide/svelte";
  import type { StockOverview } from "../api/types";
  import { fmtPct, formatLargeNumber, formatMoney, formatNumber, retTextColor } from "../format";
  import StatTile from "./StatTile.svelte";

  let {
    overview,
    canAdd = false,
    onAdd = () => {},
  }: { overview: StockOverview; canAdd?: boolean; onAdd?: () => void } = $props();

  const quote = $derived(overview.quote);
  const currency = $derived(quote.currency ?? overview.currency ?? "USD");
  const change = $derived(quote.dayChange ?? null);
  const range = $derived.by(() => {
    if (quote.fiftyTwoWeekLow === null || quote.fiftyTwoWeekLow === undefined) return "—";
    if (quote.fiftyTwoWeekHigh === null || quote.fiftyTwoWeekHigh === undefined) return "—";
    return `${formatNumber(quote.fiftyTwoWeekLow)} / ${formatNumber(quote.fiftyTwoWeekHigh)}`;
  });
  const dividendYield = $derived(
    quote.dividendYield !== null && quote.dividendYield !== undefined ? quote.dividendYield * 100 : null,
  );
</script>

<div class="stock-header banner">
  <div class="stock-title-block">
    <div class="stock-eyebrow">{quote.exchange ?? quote.fullExchangeName ?? "Stock"}</div>
    <h1>{quote.symbol}</h1>
    <div class="stock-name">{quote.name}</div>
  </div>
  <div class="stock-price-block">
    <div class="stock-price mono">{formatMoney(quote.regularMarketPrice, currency)}</div>
    <div class="stock-change mono" style:color={retTextColor(change)}>
      {change !== null && change !== undefined ? (change >= 0 ? "+" : "") + formatNumber(change) : "—"}
      <span>{fmtPct(quote.dayChangePercent)}</span>
    </div>
  </div>
  {#if canAdd}
    <button class="edit-tickers-btn stock-add-btn" onclick={onAdd}>
      <Plus class="icon" aria-hidden="true" /> Add to Watchlist
    </button>
  {/if}
</div>

<div class="stock-grid stock-kpis">
  <StatTile label="Market Cap" value={formatLargeNumber(quote.marketCap)} />
  <StatTile label="P/E" value={formatNumber(quote.trailingPE)} />
  <StatTile label="Div Yield" value={fmtPct(dividendYield)} />
  <StatTile label="52W Range" value={range} />
</div>
