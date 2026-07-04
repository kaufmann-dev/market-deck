<script lang="ts">
  import LegalLinks from "./LegalLinks.svelte";
  import { auth } from "../stores/auth.svelte";

  let { onLoggedIn }: { onLoggedIn: () => Promise<void> } = $props();

  let email = $state("");
  let password = $state("");
  let error = $state("");

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    error = "";
    try {
      await auth.login(email.trim(), password);
      await onLoggedIn();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

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
    <form class="login-form" onsubmit={submit}>
      <label for="login-email">Email</label>
      <input id="login-email" type="email" autocomplete="username" required bind:value={email} />
      <label for="login-password">Password</label>
      <input
        id="login-password"
        type="password"
        autocomplete="current-password"
        required
        bind:value={password}
      />
      <div class="login-error" aria-live="polite">{error}</div>
      <button type="submit" class="login-submit">Login</button>
    </form>
    <div class="demo-login">
      <button type="button" onclick={demoLogin}>Login as Demo</button>
    </div>
  </div>
  <LegalLinks class="login-legal-links" />
</div>
