<script lang="ts">
  import type { ListInfo } from "../api/types";
  import { app } from "../stores/app.svelte";

  let { list }: { list: ListInfo } = $props();

  const LOOKBACKS = [1, 3, 6, 12];
  const TOP_NS = [1, 2, 3, 4, 5];

  const tagOptions = $derived.by(() => {
    const tags = new Set(list.items.map((item) => item.tag).filter((tag) => tag));
    return [...tags].sort();
  });
</script>

<div class="controls">
  <div class="cg">
    <span class="cg-label">Lookback Period</span>
    <div class="btn-group">
      {#each LOOKBACKS as n (n)}
        <button class={app.lb === n ? "a-amber" : ""} onclick={() => (app.lb = n)}>{n}M</button>
      {/each}
    </div>
  </div>
  <div class="cg">
    <span class="cg-label">Highlighted Assets</span>
    <div class="btn-group">
      {#each TOP_NS as n (n)}
        <button class={app.topN === n ? "a-blue" : ""} onclick={() => (app.topN = n)}>{n}</button>
      {/each}
    </div>
  </div>
  {#if list.showTag !== false}
    <div class="cg">
      <label class="cg-label" for="tag-filter-select">Filter by Tag</label>
      <div class="btn-group">
        <select id="tag-filter-select" bind:value={app.tagFilter}>
          <option value="All">All Tags</option>
          {#each tagOptions as tag (tag)}
            <option value={tag}>{tag}</option>
          {/each}
        </select>
      </div>
    </div>
  {/if}
  <div class="cg cg-right">
    <span class="cg-label">View</span>
    <div class="btn-group">
      <button class={app.viewTab === "r" ? "a-purple" : ""} onclick={() => (app.viewTab = "r")}>
        Rankings
      </button>
      <button class={app.viewTab === "h" ? "a-purple" : ""} onclick={() => (app.viewTab = "h")}>
        Monthly Heatmap
      </button>
    </div>
  </div>
</div>
