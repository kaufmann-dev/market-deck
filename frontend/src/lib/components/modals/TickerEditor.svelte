<script lang="ts">
  import { Check, Plus, X } from "@lucide/svelte";
  import { apiFetch, postJson, putJson } from "../../api/client";
  import type { TickerItem } from "../../api/types";
  import { app, normalizeTag, sortedTags } from "../../stores/app.svelte";

  let { slug, onClose }: { slug: string; onClose: () => void } = $props();

  const list = $derived(app.lists[slug]);
  const tags = $derived(sortedTags(list));
  const hasTags = $derived(tags.length > 0);

  interface RowDraft {
    symbol: string;
    name: string;
    tag: string;
    currency: string;
  }

  let drafts = $state<Record<number, RowDraft>>({});
  let savedIds = $state<Record<number, boolean>>({});

  $effect(() => {
    const next: Record<number, RowDraft> = {};
    for (const item of list?.items ?? []) {
      next[item.id] = drafts[item.id] ?? {
        symbol: item.ticker,
        name: item.name,
        tag: item.tag,
        currency: item.currency,
      };
    }
    drafts = next;
  });

  let addSymbol = $state("");
  let addName = $state("");
  let addTag = $state("");
  let addCurrency = $state("");

  async function saveTicker(item: TickerItem) {
    const draft = drafts[item.id];
    if (!draft) return;
    try {
      await putJson(`/api/tickers/${item.id}`, {
        symbol: draft.symbol,
        name: draft.name,
        tag: draft.tag,
        currency: draft.currency,
      });
      savedIds = { ...savedIds, [item.id]: true };
      setTimeout(() => {
        savedIds = { ...savedIds, [item.id]: false };
      }, 800);
      item.ticker = draft.symbol;
      item.name = draft.name;
      item.tag = normalizeTag(draft.tag);
      item.currency = draft.currency;
    } catch (e) {
      alert("Error saving ticker: " + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function deleteTicker(item: TickerItem) {
    if (!confirm("Remove this ticker?")) return;
    try {
      await apiFetch(`/api/tickers/${item.id}`, { method: "DELETE" });
      list.items = list.items.filter((t) => t.id !== item.id);
    } catch (e) {
      alert("Error deleting ticker: " + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function addTicker() {
    const symbol = addSymbol.trim();
    const name = addName.trim();
    const tag = normalizeTag(addTag || tags[0]?.tag);
    const currency = addCurrency.trim().toUpperCase() || "USD";
    if (!symbol || !name) {
      alert("Symbol and Name are required.");
      return;
    }
    if (!tag) {
      alert("Tag is unavailable.");
      return;
    }
    try {
      const data = await postJson<{ id: number }>(`/api/lists/${slug}/tickers`, {
        symbol,
        name,
        tag,
        currency,
      });
      list.items.push({ id: data.id, ticker: symbol, name, tag, currency });
      addSymbol = "";
      addName = "";
      addTag = tags[0]?.tag ?? "";
      addCurrency = "";
    } catch (e) {
      alert("Error adding ticker: " + (e instanceof Error ? e.message : String(e)));
    }
  }

  function close() {
    // Edits may have changed symbols/currencies; refetch metrics for this list.
    app.invalidateMetrics(slug);
    void app.loadMetrics(slug);
    onClose();
  }
</script>

<div class="editor-overlay-root">
  <div class="editor-backdrop" role="presentation" onclick={close}></div>
  <div id="editor-panel">
    <div class="editor-header">
      <h2>Edit Tickers</h2>
      <button onclick={close} class="editor-close-btn">
        <X class="icon" aria-hidden="true" /> Close
      </button>
    </div>

    <div class="editor-section">
      <div class="editor-section-title">
        Tickers in <span class="editor-list-name">{list?.name ?? ""}</span>
      </div>
      <div id="ed-tickers">
        {#if !hasTags}
          <div class="editor-empty">No list tags available.</div>
        {:else}
          {#each list?.items ?? [] as item, index (item.id)}
            {#if drafts[item.id]}
              <div class="ed-ticker-row">
                <span class="ed-row-index">{index + 1}</span>
                <input class="ed-sym" bind:value={drafts[item.id].symbol} aria-label="Symbol" />
                <input class="ed-name" bind:value={drafts[item.id].name} aria-label="Name" />
                <select class="ed-tag" bind:value={drafts[item.id].tag} aria-label="Tag">
                  {#each tags as tag (tag.tag)}
                    <option value={tag.tag}>{tag.tag}</option>
                  {/each}
                </select>
                <input
                  class="ed-cur"
                  bind:value={drafts[item.id].currency}
                  maxlength="3"
                  aria-label="Currency"
                />
                <button
                  class="ed-btn-save"
                  class:ed-btn-saved={savedIds[item.id]}
                  onclick={() => saveTicker(item)}
                >
                  {#if savedIds[item.id]}
                    <Check class="icon" aria-hidden="true" />
                  {:else}
                    Save
                  {/if}
                </button>
                <button
                  class="ed-btn-del"
                  onclick={() => deleteTicker(item)}
                  aria-label={`Delete ${item.ticker}`}
                >
                  <X class="icon" aria-hidden="true" />
                </button>
              </div>
            {/if}
          {/each}
        {/if}
      </div>
      <div class="ed-add-ticker-box">
        <div class="editor-section-title ed-add-title">Add Ticker</div>
        <div class="ed-add-fields">
          <input class="ed-add-symbol" type="text" placeholder="AAPL" bind:value={addSymbol} aria-label="New symbol" />
          <input class="ed-add-name" type="text" placeholder="Apple Inc." bind:value={addName} aria-label="New name" />
          <select class="ed-add-tag" bind:value={addTag} disabled={!hasTags} aria-label="New tag">
            {#each tags as tag (tag.tag)}
              <option value={tag.tag}>{tag.tag}</option>
            {/each}
          </select>
          <input
            class="ed-add-cur"
            type="text"
            placeholder="USD"
            maxlength="3"
            bind:value={addCurrency}
            aria-label="New currency"
          />
          <button onclick={addTicker} class="ed-btn-save ed-add-btn" disabled={!hasTags}>
            <Plus class="icon" aria-hidden="true" /> Add
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
