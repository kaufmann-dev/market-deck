<script lang="ts">
  import { Plus, X } from "@lucide/svelte";
  import { apiFetch, postJson, putJson } from "../api/client";
  import { autoTagColors, hexFromTagColors } from "../format";
  import { app, normalizeTag, sortedTags } from "../stores/app.svelte";

  let newTagNames = $state<Record<string, string>>({});
  let newTagColors = $state<Record<string, string>>({});

  $effect(() => {
    for (const slug of Object.keys(app.lists)) {
      if (!(slug in newTagColors)) newTagColors[slug] = "#68d391";
      if (!(slug in newTagNames)) newTagNames[slug] = "";
    }
  });

  async function updateColor(slug: string, tag: string, hex: string) {
    const normalized = normalizeTag(tag);
    const colors = autoTagColors(hex);
    try {
      await putJson(`/api/lists/${encodeURIComponent(slug)}/tags/${encodeURIComponent(normalized)}`, colors);
      const list = app.lists[slug];
      const info = list.tags.find((item) => normalizeTag(item.tag) === normalized);
      if (info) Object.assign(info, colors);
    } catch (e) {
      alert("Error: " + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function deleteTag(slug: string, tag: string) {
    const normalized = normalizeTag(tag);
    if (!confirm(`Delete tag "${normalized}" from this list?`)) return;
    try {
      await apiFetch(`/api/lists/${encodeURIComponent(slug)}/tags/${encodeURIComponent(normalized)}`, {
        method: "DELETE",
      });
      const list = app.lists[slug];
      list.tags = list.tags.filter((item) => normalizeTag(item.tag) !== normalized);
    } catch (e) {
      alert("Error: " + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function addTag(event: SubmitEvent, slug: string) {
    event.preventDefault();
    const name = normalizeTag(newTagNames[slug] ?? "");
    const hex = newTagColors[slug] ?? "#68d391";
    if (!name) {
      alert("Tag name is required.");
      return;
    }
    const colors = autoTagColors(hex);
    try {
      const data = await postJson<{ tag: string }>(
        `/api/lists/${encodeURIComponent(slug)}/tags`,
        { tag: name, ...colors },
      );
      const list = app.lists[slug];
      const nextOrder = Math.max(-1, ...sortedTags(list).map((item) => item.sortOrder ?? 0)) + 1;
      list.tags = [...list.tags, { tag: data.tag || name, ...colors, sortOrder: nextOrder }];
      newTagNames[slug] = "";
      newTagColors[slug] = "#68d391";
    } catch (e) {
      alert("Error: " + (e instanceof Error ? e.message : String(e)));
    }
  }
</script>

<div class="tag-color-grid">
  {#each Object.entries(app.lists) as [slug, list] (slug)}
    {@const tags = sortedTags(list)}
    <section class="tag-list-panel">
      <div class="tag-list-header">
        <div>
          <div class="tag-list-title">{list.name}</div>
          <div class="tag-list-meta">{tags.length} {tags.length === 1 ? "tag" : "tags"}</div>
        </div>
      </div>
      <div class="tag-chip-grid">
        {#if tags.length === 0}
          <div class="tag-empty">No tags yet</div>
        {:else}
          {#each tags as tagInfo (tagInfo.tag)}
            <div class="tag-color-row">
              <input
                type="color"
                class="tag-color-input"
                value={hexFromTagColors(tagInfo)}
                onchange={(e) => updateColor(slug, tagInfo.tag, (e.currentTarget as HTMLInputElement).value)}
                aria-label={`Color for ${tagInfo.tag}`}
              />
              <span class="tag-color-name">{tagInfo.tag}</span>
              <button
                class="tag-color-del"
                onclick={() => deleteTag(slug, tagInfo.tag)}
                title={`Delete ${tagInfo.tag}`}
                aria-label={`Delete ${tagInfo.tag}`}
              >
                <X class="icon" aria-hidden="true" />
              </button>
            </div>
          {/each}
        {/if}
      </div>
      <form class="tag-add-row" onsubmit={(e) => addTag(e, slug)}>
        <input
          name="tag"
          type="text"
          placeholder="TAG NAME"
          bind:value={newTagNames[slug]}
          oninput={() => (newTagNames[slug] = (newTagNames[slug] ?? "").toUpperCase())}
        />
        <input name="color" type="color" bind:value={newTagColors[slug]} aria-label="New tag color" />
        <button type="submit"><Plus class="icon" aria-hidden="true" /> Add</button>
      </form>
    </section>
  {/each}
</div>
