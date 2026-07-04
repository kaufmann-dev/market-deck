<script lang="ts">
  import { Circle, CircleDot } from "@lucide/svelte";
  import type { ListInfo } from "../api/types";
  import { currencySymbol, fmtPct, formatBaseDate, retTextColor, tagStyle } from "../format";
  import type { ScoredRow } from "../scoring";
  import { app } from "../stores/app.svelte";

  let { rows, list }: { rows: ScoredRow[]; list: ListInfo } = $props();

  const sym = $derived(currencySymbol(app.baseCurrency));
  const showTag = $derived(list.showTag !== false);

  function rankClass(row: ScoredRow): string {
    if (row.rank <= app.topN && row.score !== null) return "rb-buy";
    return row.rank <= app.topN + 2 ? "rb-near" : "rb-rest";
  }

  function isBuy(row: ScoredRow): boolean {
    return row.rank <= app.topN && row.score !== null;
  }

  function barPct(row: ScoredRow): number {
    return row.score !== null ? Math.min((Math.abs(row.score) / 25) * 100, 100) : 0;
  }
</script>

<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>Rank</th>
        <th>Name</th>
        <th>Ticker</th>
        {#if showTag}
          <th>Tag</th>
        {/if}
        <th>{app.lb}M Return</th>
        <th>Current Price</th>
        <th>Group</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row (row.id)}
        <tr class="clickable-row" class:row-buy={isBuy(row)} onclick={() => app.openStock(row.ticker)}>
          <td><span class="rb {rankClass(row)}">{row.rank}</span></td>
          <td><div class="cell-name"><span>{row.name}</span></div></td>
          <td>
            <button
              class="ticker stock-link"
              onclick={(event) => {
                event.stopPropagation();
                app.openStock(row.ticker);
              }}
            >
              {row.ticker}
            </button>
          </td>
          {#if showTag}
            <td><span class="tag" style={tagStyle(row.tag, list)}>{row.tag}</span></td>
          {/if}
          <td>
            <div class="bar-wrap">
              <div class="bar-track">
                <div
                  class="bar-fill"
                  style:width="{barPct(row)}%"
                  style:background={row.score !== null && row.score >= 0 ? "#68d391" : "#fc8181"}
                ></div>
              </div>
              <span class="mono ret-value" style:color={retTextColor(row.score)}>
                {fmtPct(row.score)}
              </span>
            </div>
            {#if row.basePrice !== null && row.baseDate}
              <div class="price-info">
                from {sym}{row.basePrice.toFixed(2)} on {formatBaseDate(row.baseDate)}
              </div>
            {/if}
          </td>
          <td>
            <span class="mono price-cell">
              {row.currentPrice !== null ? sym + row.currentPrice.toFixed(2) : "—"}
            </span>
          </td>
          <td>
            {#if isBuy(row)}
              <span class="sig-buy"><CircleDot class="icon" aria-hidden="true" /> TOP {app.topN}</span>
            {:else}
              <span class="sig-skip"><Circle class="icon" aria-hidden="true" /> OTHER</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
