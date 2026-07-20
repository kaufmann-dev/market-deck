<script lang="ts">
  import LegalLinks from "./LegalLinks.svelte";
  import { auth } from "../stores/auth.svelte";

  let { onLoggedIn }: { onLoggedIn: () => Promise<void> } = $props();

  let error = $state("");

  async function demoLogin() {
    error = "";
    try {
      await auth.loginAsDemo();
      await onLoggedIn();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
</script>

<div class="login-view">
  <div class="login-panel">
    <div class="login-kicker">Market Deck</div>
    <h1>Sign In</h1>
    <a class="login-submit" href="/api/auth/login">Sign in as Admin</a>
    <div class="demo-login">
      <button type="button" onclick={demoLogin}>Login as Demo</button>
    </div>
    <div class="login-error" aria-live="polite">{error}</div>
  </div>
  <LegalLinks class="login-legal-links" />
</div>
