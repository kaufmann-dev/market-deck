<script lang="ts">
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

  let mobileNavOpen = $state(false);

  const loggedIn = $derived(auth.currentUser !== null);

  $effect(() => {
    document.body.classList.toggle("auth-ready", loggedIn);
    document.body.classList.toggle("auth-pending", !loggedIn);
  });

  // Session bootstrap: validate a stored token, then load app data.
  $effect(() => {
    void (async () => {
      if (await auth.restore()) {
        await app.loadInit();
        app.syncRoute(router.route);
      }
    })();
  });

  $effect(() => {
    if (!loggedIn) return;
    app.syncRoute(router.route);
  });

  async function handleLoggedIn() {
    await app.loadInit();
    app.syncRoute(router.route);
  }

  function handleLogout() {
    auth.logout();
    app.reset();
  }
</script>

{#if auth.restoring}
  <!-- brief blank shell while the stored token is validated -->
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
