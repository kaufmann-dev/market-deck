<script lang="ts">
  import { formatLargeNumber, formatNumber, formatUnixDate } from "../format";

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
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
      .replace(/_/g, " ")
      .replace(/^./, (value) => value.toUpperCase());
  }

  function isDateKey(key: string): boolean {
    return /date/i.test(key);
  }

  function display(key: string, value: unknown): string {
    if (value === null || value === undefined) return "—";
    if (typeof value === "object") {
      const raw = (value as { raw?: unknown }).raw;
      if (raw !== undefined) return display(key, raw);
      const fmt = (value as { fmt?: unknown }).fmt;
      if (fmt !== undefined && fmt !== null) return String(fmt);
      return "—";
    }
    if (typeof value === "number") {
      if (isDateKey(key)) return formatUnixDate(value);
      return Math.abs(value) >= 100000 ? formatLargeNumber(value) : formatNumber(value);
    }
    if (typeof value === "string") return value;
    return "—";
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
              <td class:mono={typeof row[column] === "number"}>{display(column, row[column])}</td>
            {/each}
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>
