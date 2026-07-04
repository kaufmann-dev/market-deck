<script lang="ts">
  let { class: className = "" }: { class?: string } = $props();
</script>

<nav class="legal-links {className}" aria-label="Legal links">
  <a href="https://legal.kaufmann.dev/imprint?site=marketdeck.kaufmann.dev">Imprint</a>
  <a href="https://legal.kaufmann.dev/privacy?site=marketdeck.kaufmann.dev">Privacy</a>
</nav>
