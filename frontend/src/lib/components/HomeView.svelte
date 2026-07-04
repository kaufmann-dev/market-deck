<script lang="ts">
  import { Pencil, Plus } from "@lucide/svelte";
  import ListEditModal from "./modals/ListEditModal.svelte";
  import TagColorEditor from "./TagColorEditor.svelte";
  import { app } from "../stores/app.svelte";
  import { auth } from "../stores/auth.svelte";

  const CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY"];

  let editModal = $state<{ open: boolean; slug: string | null }>({ open: false, slug: null });

  async function changeCurrency(event: Event) {
    const value = (event.currentTarget as HTMLSelectElement).value;
    try {
      await app.setBaseCurrency(value);
    } catch (e) {
      alert("Error saving currency: " + (e instanceof Error ? e.message : String(e)));
    }
  }
</script>

<div class="view-home">
  <div class="home-header">
    <h1 class="home-title">Market Deck</h1>
    <div class="home-currency">
      <label for="home-currency-input">Base Currency</label>
      <select id="home-currency-input" value={app.baseCurrency} onchange={changeCurrency}>
        {#each CURRENCIES as currency (currency)}
          <option value={currency}>{currency}</option>
        {/each}
      </select>
    </div>
  </div>

  <div class="home-section-title">Watchlists</div>
  <div class="home-grid">
    {#each Object.entries(app.lists) as [slug, list] (slug)}
      <div
        class="wl-card"
        role="button"
        tabindex="0"
        onclick={() => app.openList(slug)}
        onkeydown={(e) => (e.key === "Enter" || e.key === " ") && app.openList(slug)}
      >
        {#if auth.isAdmin}
          <button
            class="wl-card-edit"
            onclick={(e) => {
              e.stopPropagation();
              editModal = { open: true, slug };
            }}
            title="Edit list"
            aria-label="Edit list"
          >
            <Pencil class="icon" aria-hidden="true" />
          </button>
        {/if}
        <div class="wl-card-name">{list.name}</div>
        <div class="wl-card-meta">
          <span class="wl-card-count">{list.items.length} tickers</span>
          <span class="wl-card-category">{list.category}</span>
        </div>
        {#if list.description}
          <div class="wl-card-desc">{list.description}</div>
        {/if}
      </div>
    {/each}
    {#if auth.isAdmin}
      <div
        class="wl-card-new"
        role="button"
        tabindex="0"
        onclick={() => (editModal = { open: true, slug: null })}
        onkeydown={(e) => (e.key === "Enter" || e.key === " ") && (editModal = { open: true, slug: null })}
      >
        <div class="wl-card-new-icon"><Plus class="icon" aria-hidden="true" /></div>
        <div class="wl-card-new-label">Create New List</div>
      </div>
    {/if}
  </div>

  {#if auth.isAdmin}
    <div class="tag-section">
      <div class="home-section-title">List Tags</div>
      <TagColorEditor />
    </div>
  {/if}
</div>

{#if editModal.open}
  <ListEditModal slug={editModal.slug} onClose={() => (editModal = { open: false, slug: null })} />
{/if}
