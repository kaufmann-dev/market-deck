<script lang="ts">
  let { open = $bindable(false) }: { open?: boolean } = $props();
</script>

<button
  class="mobile-nav-toggle"
  class:open
  aria-label={open ? "Close navigation" : "Open navigation"}
  aria-expanded={open}
  onclick={() => (open = !open)}
>
  <span class="hamburger-line"></span>
  <span class="hamburger-line"></span>
  <span class="hamburger-line"></span>
</button>
<div
  class="mobile-nav-backdrop"
  class:open
  role="presentation"
  onclick={() => (open = false)}
></div>
