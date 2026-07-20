<script lang="ts">
  import { onMount } from "svelte";
  import LegalLinks from "./lib/components/LegalLinks.svelte";
  import LoginView from "./lib/components/LoginView.svelte";
  import MobileNav from "./lib/components/MobileNav.svelte";
  import SessionBar from "./lib/components/SessionBar.svelte";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import HomeView from "./lib/components/HomeView.svelte";
  import ListView from "./lib/components/ListView.svelte";
  import StockView from "./lib/components/StockView.svelte";
  import { app } from "./lib/stores/app.svelte";
  import { auth } from "./lib/stores/auth.svelte";
  import { router } from "./lib/stores/router.svelte";
  import { apiFetch } from "./lib/api/client";

  let mobileNavOpen = $state(false);
  let lastActivitySignalAt = -Infinity;

  const activitySignalInterval = 5 * 60 * 1000;

  const loggedIn = $derived(auth.currentUser !== null);

  function syncBodyAuthClass() {
    document.body.classList.toggle("auth-ready", loggedIn);
    document.body.classList.toggle("auth-pending", !loggedIn);
  }

  $effect(syncBodyAuthClass);

  function syncActiveRoute() {
    if (!loggedIn) return;
    app.syncRoute(router.route);
  }

  $effect(syncActiveRoute);

  async function restoreSession() {
    if (await auth.restore()) {
      await app.loadInit();
      app.syncRoute(router.route);
    }
  }

  // Restore the cookie-backed session exactly once when the SPA mounts.
  onMount(() => {
    void restoreSession();
  });

  async function handleLoggedIn() {
    await app.loadInit();
    app.syncRoute(router.route);
  }

  function handleLogout() {
    auth.logout();
    app.reset();
  }

  function signalUserActivity(event: Event) {
    if (!loggedIn || !event.isTrusted) return;

    const now = Date.now();
    if (now - lastActivitySignalAt < activitySignalInterval) return;
    lastActivitySignalAt = now;

    void apiFetch("/api/auth/activity", {
      method: "POST",
      headers: { "x-marketdeck-user-activity": "1" },
      keepalive: true,
    }).catch(() => {});
  }
</script>

<svelte:window
  onpointerdown={signalUserActivity}
  onkeydown={signalUserActivity}
  onclick={signalUserActivity}
/>

{#if auth.restoring}
  <!-- brief blank shell while the session is restored -->
{:else if !loggedIn}
  <LoginView onLoggedIn={handleLoggedIn} />
{:else}
  <MobileNav bind:open={mobileNavOpen} />
  <Sidebar bind:mobileNavOpen />
  <div class="main">
    <SessionBar onLogout={handleLogout} />
    {#if router.route.name === "home"}
      <HomeView />
    {:else if router.route.name === "list"}
      <ListView />
    {:else}
      <StockView symbol={router.route.params.symbol} />
    {/if}
    <LegalLinks class="app-legal-links" />
  </div>
{/if}
