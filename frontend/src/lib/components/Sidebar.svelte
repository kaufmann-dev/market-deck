<script lang="ts">
  import type { ListInfo } from "../api/types";
  import { app, normalizeCategory } from "../stores/app.svelte";

  let { mobileNavOpen = $bindable(false) }: { mobileNavOpen?: boolean } = $props();

  interface Group {
    label: string;
    items: { slug: string; list: ListInfo }[];
  }

  const groups = $derived.by(() => {
    const grouped = new Map<string, Group>();
    for (const [slug, list] of Object.entries(app.lists)) {
      const label = normalizeCategory(list.category);
      const key = label.toLocaleLowerCase();
      if (!grouped.has(key)) grouped.set(key, { label, items: [] });
      grouped.get(key)!.items.push({ slug, list });
    }
    return [...grouped.values()];
  });

  function goHome() {
    mobileNavOpen = false;
    app.showHome();
  }

  function openList(slug: string) {
    mobileNavOpen = false;
    app.openList(slug);
  }
</script>

<nav class="sidebar" class:open={mobileNavOpen}>
  <button class="sidebar-home-btn" class:active={app.currentView === "home"} onclick={goHome}>
    Market Deck
  </button>
  {#each groups as group (group.label)}
    <div class="sidebar-section">{group.label}</div>
    {#each group.items as { slug, list } (slug)}
      <button
        class="list-btn"
        class:active={app.activeList === slug && app.currentView === "list"}
        onclick={() => openList(slug)}
      >
        <span>{list.shortName}</span>
        <span class="count">{list.items.length}</span>
      </button>
    {/each}
  {/each}
</nav>
