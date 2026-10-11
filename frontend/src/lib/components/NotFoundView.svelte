<script lang="ts">
  import { ArrowLeft } from "@lucide/svelte";
  import { app } from "../stores/app.svelte";

  let { title, message }: { title: string; message: string } = $props();
</script>

<div class="view-not-found">
  <div class="list-topbar">
    <button class="breadcrumb-btn" onclick={() => app.showHome()}>
      <ArrowLeft class="icon" aria-hidden="true" /> Home
    </button>
  </div>
  <h1 class="list-title">{title}</h1>
  <p class="subtitle">{message}</p>
</div>
