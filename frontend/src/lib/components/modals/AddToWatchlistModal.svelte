<script lang="ts">
  import { Plus, X } from "@lucide/svelte";
  import { postJson } from "../../api/client";
  import type { StockQuote } from "../../api/types";
  import { app, sortedTags } from "../../stores/app.svelte";

  let { quote, onClose }: { quote: StockQuote; onClose: () => void } = $props();

  const listEntries = $derived(Object.entries(app.lists));
  let selectedSlug = $state("");
  let selectedTag = $state("");
  let saving = $state(false);
  let error = $state("");

  const tags = $derived(sortedTags(selectedSlug ? app.lists[selectedSlug] : null));

  $effect(() => {
    if (!selectedSlug && listEntries[0]) selectedSlug = listEntries[0][0];
    if (!selectedTag || !tags.some((tag) => tag.tag === selectedTag)) {
      selectedTag = tags[0]?.tag ?? "";
    }
  });

  async function add() {
    if (!selectedSlug || !selectedTag) return;
    saving = true;
    error = "";
    try {
      await postJson<{ id: number }>(`/api/lists/${encodeURIComponent(selectedSlug)}/tickers`, {
        symbol: quote.symbol,
        name: quote.name,
        tag: selectedTag,
        currency: quote.currency ?? "USD",
      });
      await app.refresh({ invalidate: false });
      onClose();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }
</script>

<div class="modal-overlay">
  <div class="modal-backdrop" role="presentation" onclick={onClose}></div>
  <div class="modal-box">
    <div class="modal-header">
      <h2>Add {quote.symbol}</h2>
      <button onclick={onClose} class="modal-close-btn" aria-label="Close">
        <X class="icon" aria-hidden="true" />
      </button>
    </div>

    <div class="modal-fields">
      <div class="modal-field">
        <label for="add-stock-list">Watchlist</label>
        <select id="add-stock-list" bind:value={selectedSlug}>
          {#each listEntries as [slug, list] (slug)}
            <option value={slug}>{list.name}</option>
          {/each}
        </select>
      </div>
      <div class="modal-field">
        <label for="add-stock-tag">Tag</label>
        <select id="add-stock-tag" bind:value={selectedTag} disabled={tags.length === 0}>
          {#each tags as tag (tag.tag)}
            <option value={tag.tag}>{tag.tag}</option>
          {/each}
        </select>
      </div>
      {#if error}
        <div class="login-error" role="alert">{error}</div>
      {/if}
      {#if tags.length === 0}
        <div class="panel-empty">Selected watchlist has no defined tags.</div>
      {/if}
    </div>

    <div class="modal-actions">
      <button class="btn-green" onclick={add} disabled={saving || tags.length === 0}>
        <Plus class="icon" aria-hidden="true" /> {saving ? "Adding" : "Add"}
      </button>
      <button class="btn-muted" onclick={onClose}>Cancel</button>
    </div>
  </div>
</div>
