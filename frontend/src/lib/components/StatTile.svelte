<script lang="ts">
  let {
    label,
    value,
    sub = "",
    tone = "neutral",
  }: { label: string; value: string; sub?: string; tone?: "neutral" | "positive" | "negative" } = $props();
</script>

<div class="stat-tile" data-tone={tone}>
  <div class="stat-label">{label}</div>
  <div class="stat-value mono">{value}</div>
  {#if sub}
    <div class="stat-sub">{sub}</div>
  {/if}
</div>
