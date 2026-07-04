<script lang="ts">
  import type { Technicals } from "../api/types";
  import { formatLargeNumber, formatNumber, fmtPct, retTextColor } from "../format";
  import StatTile from "./StatTile.svelte";

  let { technicals = {} }: { technicals?: Technicals } = $props();

  const rsiSignal = $derived.by(() => {
    const rsi = technicals.rsi14;
    if (rsi === null || rsi === undefined) return "—";
    if (rsi >= 70) return "Overbought";
    if (rsi <= 30) return "Oversold";
    return "Neutral";
  });

  const macdValue = $derived(technicals.macd?.histogram ?? null);
  const percentFromHigh = $derived(technicals.percentFromHigh ?? null);
</script>

<div class="stock-grid">
  <StatTile label="SMA 20" value={formatNumber(technicals.sma20)} />
  <StatTile label="SMA 50" value={formatNumber(technicals.sma50)} />
  <StatTile label="SMA 200" value={formatNumber(technicals.sma200)} />
  <StatTile label="RSI 14" value={formatNumber(technicals.rsi14)} sub={rsiSignal} />
  <StatTile
    label="MACD Hist"
    value={formatNumber(macdValue, 4)}
    tone={macdValue !== null && macdValue >= 0 ? "positive" : "negative"}
  />
  <StatTile label="Avg Vol 20" value={formatLargeNumber(technicals.avgVolume20)} />
  <StatTile
    label="From 52W High"
    value={fmtPct(percentFromHigh)}
    tone={percentFromHigh !== null && percentFromHigh >= 0 ? "positive" : "negative"}
  />
  <StatTile label="Volatility" value={fmtPct(technicals.annualizedVolatility)} />
</div>
<div class="signal-read mono" style:color={retTextColor(macdValue)}>
  MACD {formatNumber(technicals.macd?.macd, 4)} / Signal {formatNumber(technicals.macd?.signal, 4)}
</div>
