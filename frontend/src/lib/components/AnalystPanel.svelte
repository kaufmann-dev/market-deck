<script lang="ts">
  import type { StockOverview } from "../api/types";
  import { formatMoney, formatNumber } from "../format";
  import StatTile from "./StatTile.svelte";

  let { overview }: { overview: StockOverview } = $props();

  const trend = $derived.by(() => {
    const values = overview.recommendation?.trend;
    return Array.isArray(values) ? values[0] as Record<string, number | string> : null;
  });
</script>

<div class="stock-grid">
  <StatTile
    label="Target Mean"
    value={formatMoney(overview.quote.targetMeanPrice, overview.quote.currency ?? overview.currency ?? "USD")}
  />
  <StatTile
    label="Recommendation"
    value={formatNumber(overview.financialData?.recommendationMean as number | null)}
  />
  <StatTile label="Strong Buy" value={String(trend?.strongBuy ?? "—")} />
  <StatTile label="Buy" value={String(trend?.buy ?? "—")} />
  <StatTile label="Hold" value={String(trend?.hold ?? "—")} />
  <StatTile label="Sell" value={String(trend?.sell ?? "—")} />
</div>
