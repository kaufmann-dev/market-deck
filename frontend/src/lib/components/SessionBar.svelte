<script lang="ts">
  import { LogOut } from "@lucide/svelte";
  import { auth } from "../stores/auth.svelte";

  let { onLogout }: { onLogout: () => void } = $props();
</script>

<div class="session-bar">
  <span class="session-label">{auth.sessionLabel}</span>
  <form method="POST" action="/api/auth/logout" onsubmit={onLogout}>
    <button type="submit">
      <LogOut class="icon" aria-hidden="true" />
      Logout
    </button>
  </form>
</div>
