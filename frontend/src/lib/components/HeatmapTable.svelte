<script lang="ts">
  import { fmtPct, retBgColor, retTextColor } from "../format";
  import type { ScoredRow } from "../scoring";
  import { app } from "../stores/app.svelte";

  let { rows }: { rows: ScoredRow[] } = $props();

  const monthLabels = $derived(
    rows.find((row) => row.monthly.length > 0)?.monthly.map((cell) => cell.label) ?? [],
  );

  function isBuy(row: ScoredRow): boolean {
    return row.rank <= app.topN && row.score !== null;
  }
</script>

<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th class="hm-th hm-th-name">Name</th>
        {#each monthLabels as label (label)}
          <th class="hm-th hm-th-month">{label}</th>
        {/each}
        <th class="hm-th hm-th-12m">12M</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row (row.id)}
        <tr class="hm-row clickable-row" class:row-buy={isBuy(row)} onclick={() => app.openStock(row.ticker)}>
          <td class="hm-name-cell">
            <div class="cell-name">
              <div>
                <button
                  class="ticker hm-ticker stock-link"
                  onclick={(event) => {
                    event.stopPropagation();
                    app.openStock(row.ticker);
                  }}
                >
                  {row.ticker}
                </button>
                <div class="hm-name-sub">{row.name}</div>
              </div>
            </div>
          </td>
          {#if row.monthly.length > 0}
            {#each row.monthly as cell, i (i)}
              <td class="hm-cell">
                <span
                  class="heatmap-pill"
                  style:background={cell.ret !== null ? retBgColor(cell.ret) + "22" : "transparent"}
                  style:color={cell.ret !== null ? retBgColor(cell.ret) : "#4a5568"}
                >
                  {cell.ret !== null ? (cell.ret > 0 ? "+" : "") + cell.ret.toFixed(1) : "—"}
                </span>
              </td>
            {/each}
          {:else}
            <td class="hm-no-data" colspan={monthLabels.length}>No data</td>
          {/if}
          <td class="hm-12m-cell" style:color={retTextColor(row.ret12m)}>
            {row.ret12m !== null ? fmtPct(row.ret12m) : "—"}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
