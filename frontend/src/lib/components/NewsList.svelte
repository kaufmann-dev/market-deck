<script lang="ts">
  import { ExternalLink } from "@lucide/svelte";
  import type { NewsItem } from "../api/types";
  import { formatUnixDate } from "../format";

  let { news = [] }: { news?: NewsItem[] } = $props();
</script>

<div class="news-list">
  {#if news.length === 0}
    <div class="panel-empty">No news available.</div>
  {:else}
    {#each news as item, index (`${item.link}-${index}`)}
      <a class="news-item" href={item.link} target="_blank" rel="noreferrer">
        {#if item.thumbnail}
          <img src={item.thumbnail} alt="" loading="lazy" />
        {/if}
        <span class="news-copy">
          <span class="news-title">{item.title}</span>
          <span class="news-meta">
            {item.publisher}{item.publishedAt ? ` · ${formatUnixDate(item.publishedAt)}` : ""}
          </span>
        </span>
        <ExternalLink class="icon" aria-hidden="true" />
      </a>
    {/each}
  {/if}
</div>
