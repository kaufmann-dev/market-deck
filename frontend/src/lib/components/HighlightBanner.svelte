<script lang="ts">
  import { fmtPct, retTextColor } from "../format";
  import type { ScoredRow } from "../scoring";
  import { app } from "../stores/app.svelte";

  let { rows }: { rows: ScoredRow[] } = $props();

  const selected = $derived(rows.filter((row) => row.score !== null && row.rank <= app.topN));
</script>

<div class="banner">
  <div class="banner-lbl">Highlighted Assets · Top {app.topN} · {app.lb}M Return</div>
  <div class="holdings">
    {#each selected as row (row.id)}
      <div class="hcard">
        <div>
          <div class="hcard-ticker">{row.ticker}</div>
          <div class="hcard-name">{row.name}</div>
        </div>
        <div class="hcard-score" style:color={retTextColor(row.score)}>{fmtPct(row.score)}</div>
      </div>
    {/each}
  </div>
</div>
