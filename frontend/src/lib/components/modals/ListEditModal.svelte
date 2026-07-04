<script lang="ts">
  import { X } from "@lucide/svelte";
  import { apiFetch, postJson, putJson } from "../../api/client";
  import { app, normalizeCategory } from "../../stores/app.svelte";

  let { slug, onClose }: { slug: string | null; onClose: () => void } = $props();

  const isNew = $derived(slug === null);
  const list = $derived(slug ? app.lists[slug] : null);

  let name = $state("");
  let shortName = $state("");
  let category = $state("");
  let showTag = $state(true);
  let description = $state("");

  $effect(() => {
    name = list?.name ?? "";
    shortName = list?.shortName ?? "";
    category = list?.category ?? "";
    showTag = list ? list.showTag !== false : true;
    description = list?.description ?? "";
  });

  async function save() {
    const trimmedName = name.trim();
    const trimmedShort = shortName.trim();
    if (!trimmedName || !trimmedShort) {
      alert("Name and Short Name are required.");
      return;
    }
    const body = {
      name: trimmedName,
      short_name: trimmedShort,
      category: normalizeCategory(category),
      description: description.trim(),
      show_tag: showTag,
    };
    try {
      if (isNew) {
        const newSlug = trimmedShort.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
        if (!newSlug) {
          alert("Short Name must contain letters or numbers.");
          return;
        }
        await postJson("/api/lists", { ...body, slug: newSlug, currency: app.baseCurrency });
      } else {
        await putJson(`/api/lists/${slug}`, body);
      }
      onClose();
      await app.refresh();
    } catch (e) {
      alert("Error: " + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function deleteList() {
    if (!slug || !list) return;
    if (!confirm(`Delete the entire "${list.name}" list?`)) return;
    try {
      await apiFetch(`/api/lists/${slug}`, { method: "DELETE" });
      onClose();
      await app.refresh();
    } catch (e) {
      alert("Error: " + (e instanceof Error ? e.message : String(e)));
    }
  }
</script>

<div class="modal-overlay">
  <div class="modal-backdrop" role="presentation" onclick={onClose}></div>
  <div class="modal-box">
    <div class="modal-header">
      <h2>{isNew ? "Create New List" : `Edit: ${list?.name ?? ""}`}</h2>
      <button onclick={onClose} class="modal-close-btn" aria-label="Close">
        <X class="icon" aria-hidden="true" />
      </button>
    </div>

    <div class="modal-fields">
      <div class="modal-field-group">
        <div class="modal-field">
          <label for="le-name">Name</label>
          <input id="le-name" type="text" placeholder="My Watchlist" bind:value={name} />
        </div>
        <div class="modal-field">
          <label for="le-short">Short Name</label>
          <input id="le-short" type="text" placeholder="Short" bind:value={shortName} />
        </div>
      </div>

      <div class="modal-field-group">
        <div class="modal-field">
          <label for="le-category">Category</label>
          <input
            id="le-category"
            type="text"
            placeholder="ETFS"
            bind:value={category}
            oninput={() => (category = category.toUpperCase())}
          />
        </div>
        <div class="modal-field modal-field-toggle">
          <label for="le-show-tag">Show Tag Column</label>
          <label class="toggle-switch">
            <input id="le-show-tag" type="checkbox" bind:checked={showTag} />
            <span class="toggle-track"></span>
          </label>
        </div>
      </div>

      <div class="modal-field modal-field-full">
        <label for="le-desc">Description</label>
        <textarea id="le-desc" rows="3" placeholder="Optional description…" bind:value={description}
        ></textarea>
      </div>
    </div>

    <div class="modal-actions">
      <button onclick={save} class="btn-green">Save</button>
      <button onclick={onClose} class="btn-muted">Cancel</button>
      {#if !isNew}
        <button onclick={deleteList} class="btn-red">Delete List</button>
      {/if}
    </div>
  </div>
</div>
