<script lang="ts">
  import { X } from "@lucide/svelte";
  import { putJson } from "../../api/client";

  let { onClose }: { onClose: () => void } = $props();

  let currentPassword = $state("");
  let newPassword = $state("");
  let error = $state("");

  async function save(event: SubmitEvent) {
    event.preventDefault();
    error = "";
    try {
      await putJson("/api/auth/password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      onClose();
      alert("Password changed.");
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
</script>

<div class="modal-overlay">
  <div class="modal-backdrop" role="presentation" onclick={onClose}></div>
  <div class="modal-box">
    <div class="modal-header">
      <h2>Change Password</h2>
      <button onclick={onClose} class="modal-close-btn" aria-label="Close">
        <X class="icon" aria-hidden="true" />
      </button>
    </div>
    <form onsubmit={save}>
      <div class="modal-fields">
        <div class="modal-field">
          <label for="pw-current">Current Password</label>
          <input
            id="pw-current"
            type="password"
            autocomplete="current-password"
            required
            bind:value={currentPassword}
          />
        </div>
        <div class="modal-field">
          <label for="pw-new">New Password</label>
          <input
            id="pw-new"
            type="password"
            autocomplete="new-password"
            required
            bind:value={newPassword}
          />
        </div>
        <div class="login-error" aria-live="polite">{error}</div>
      </div>
      <div class="modal-actions">
        <button type="submit" class="btn-green">Save</button>
        <button type="button" onclick={onClose} class="btn-muted">Cancel</button>
      </div>
    </form>
  </div>
</div>
