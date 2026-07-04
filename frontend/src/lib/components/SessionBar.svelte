<script lang="ts">
  import { KeyRound, LogOut } from "@lucide/svelte";
  import PasswordModal from "./modals/PasswordModal.svelte";
  import { auth } from "../stores/auth.svelte";

  let { onLogout }: { onLogout: () => void } = $props();

  let passwordModalOpen = $state(false);
</script>

<div class="session-bar">
  <span class="session-label">{auth.sessionLabel}</span>
  {#if auth.isAdmin}
    <button type="button" onclick={() => (passwordModalOpen = true)}>
      <KeyRound class="icon" aria-hidden="true" />
      <span class="label-full">Change Password</span>
      <span class="label-short">Password</span>
    </button>
  {/if}
  <button type="button" onclick={onLogout}>
    <LogOut class="icon" aria-hidden="true" />
    Logout
  </button>
</div>

{#if passwordModalOpen}
  <PasswordModal onClose={() => (passwordModalOpen = false)} />
{/if}
