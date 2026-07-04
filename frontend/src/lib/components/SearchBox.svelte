<script lang="ts">
  import { Search, X } from "@lucide/svelte";
  import { onDestroy } from "svelte";
  import { apiJson } from "../api/client";
  import type { SearchQuote, SearchResult } from "../api/types";
  import { app } from "../stores/app.svelte";

  let { onSelect = () => {} }: { onSelect?: () => void } = $props();

  let query = $state("");
  let result = $state<SearchResult | null>(null);
  let searchState = $state<"idle" | "loading" | "ok" | "error">("idle");
  let error = $state("");
  let activeIndex = $state(0);

  const quotes = $derived(result?.quotes ?? []);

  let timer: ReturnType<typeof setTimeout> | null = null;
  let controller: AbortController | null = null;

  $effect(() => {
    const term = query.trim();
    activeIndex = 0;
    if (timer) clearTimeout(timer);
    controller?.abort();
    if (term.length < 2) {
      result = null;
      searchState = "idle";
      error = "";
      return;
    }

    searchState = "loading";
    controller = new AbortController();
    timer = setTimeout(async () => {
      try {
        result = await apiJson<SearchResult>(`/api/search?q=${encodeURIComponent(term)}`, {
          signal: controller?.signal,
        });
        searchState = "ok";
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        error = e instanceof Error ? e.message : String(e);
        searchState = "error";
      }
    }, 250);

    return () => {
      if (timer) clearTimeout(timer);
      controller?.abort();
    };
  });

  onDestroy(() => {
    if (timer) clearTimeout(timer);
    controller?.abort();
  });

  function clear() {
    query = "";
    result = null;
    searchState = "idle";
    error = "";
  }

  function choose(quote: SearchQuote) {
    app.openStock(quote.symbol);
    clear();
    onSelect();
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!quotes.length && event.key !== "Escape") return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, quotes.length - 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (quotes[activeIndex]) choose(quotes[activeIndex]);
    } else if (event.key === "Escape") {
      clear();
    }
  }
</script>

<div class="search-box">
  <label class="sr-only" for="global-symbol-search">Search symbol</label>
  <div class="search-input-wrap">
    <Search class="icon search-icon" aria-hidden="true" />
    <input
      id="global-symbol-search"
      type="search"
      placeholder="Search symbol"
      bind:value={query}
      onkeydown={handleKeydown}
      autocomplete="off"
      aria-autocomplete="list"
    />
    {#if query}
      <button class="search-clear" onclick={clear} aria-label="Clear search">
        <X class="icon" aria-hidden="true" />
      </button>
    {/if}
  </div>

  {#if query.trim().length >= 2}
    <div class="search-results" id="global-symbol-search-results" role="listbox">
      {#if searchState === "loading"}
        <div class="search-status">Loading</div>
      {:else if searchState === "error"}
        <div class="search-status search-status-error">{error}</div>
      {:else if quotes.length === 0}
        <div class="search-status">No matches</div>
      {:else}
        {#each quotes as quote, index (quote.symbol)}
          <button
            class="search-result"
            class:active={index === activeIndex}
            role="option"
            aria-selected={index === activeIndex}
            onmouseenter={() => (activeIndex = index)}
            onclick={() => choose(quote)}
          >
            <span class="search-result-symbol">{quote.symbol}</span>
            <span class="search-result-name">{quote.name}</span>
            <span class="search-result-exchange">{quote.exchange ?? quote.type ?? ""}</span>
          </button>
        {/each}
      {/if}
    </div>
  {/if}
</div>
