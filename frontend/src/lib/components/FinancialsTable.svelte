<script lang="ts">
  import { formatLargeNumber, formatNumber } from "../format";

  let {
    caption,
    rows = [],
  }: { caption: string; rows?: Record<string, unknown>[] } = $props();

  const columns = $derived.by(() => {
    const keys = new Set<string>();
    for (const row of rows.slice(0, 4)) {
      for (const key of Object.keys(row)) {
        if (key !== "maxAge") keys.add(key);
      }
    }
    return [...keys].slice(0, 8);
  });

  function label(key: string): string {
    return key
      .replace(/([A-Z])/g, " $1")
      .replace(/_/g, " ")
      .replace(/^./, (value) => value.toUpperCase());
  }

  function display(value: unknown): string {
    if (value === null || value === undefined) return "—";
    if (typeof value === "number") return Math.abs(value) >= 100000 ? formatLargeNumber(value) : formatNumber(value);
    if (typeof value === "string") return value;
    if (typeof value === "object" && "fmt" in value) return String((value as { fmt?: unknown }).fmt ?? "—");
    return String(value);
  }
</script>

<div class="table-wrap stock-table-wrap">
  <table aria-label={caption}>
    <caption class="sr-only">{caption}</caption>
    <thead>
      <tr>
        {#each columns as column (column)}
          <th>{label(column)}</th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#if rows.length === 0}
        <tr>
          <td class="panel-empty" colspan={Math.max(columns.length, 1)}>No statement data available.</td>
        </tr>
      {:else}
        {#each rows as row, index (index)}
          <tr>
            {#each columns as column (column)}
              <td class:mono={typeof row[column] === "number"}>{display(row[column])}</td>
            {/each}
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>
