<script lang="ts">
  import { ArrowLeft } from "@lucide/svelte";
  import { app } from "../stores/app.svelte";
  import { auth } from "../stores/auth.svelte";
  import {
    formatLargeNumber,
    formatMoney,
    formatNumber,
    fmtPct,
  } from "../format";
  import AddToWatchlistModal from "./modals/AddToWatchlistModal.svelte";
  import AnalystPanel from "./AnalystPanel.svelte";
  import FinancialsTable from "./FinancialsTable.svelte";
  import NewsList from "./NewsList.svelte";
  import StockChart from "./StockChart.svelte";
  import StockHeader from "./StockHeader.svelte";
  import TechnicalsPanel from "./TechnicalsPanel.svelte";

  let { symbol }: { symbol: string } = $props();

  let chartRange = $state("1y");
  let lastSymbol = $state("");
  let addModalOpen = $state(false);
  let financialsLoaded = $state(false);
  let financialPeriod = $state<"annual" | "quarterly">("annual");

  const normalized = $derived(String(symbol ?? "").trim().toUpperCase());
  const overview = $derived(app.stockOverview[normalized] ?? null);
  const overviewState = $derived(app.stockOverviewState(normalized));
  const chart = $derived(app.chartFor(normalized, chartRange));
  const chartState = $derived(app.stockChartState(normalized, chartRange));
  const news = $derived(app.stockNews[normalized] ?? []);
  const newsState = $derived(app.stockNewsState(normalized));
  const financials = $derived(app.stockFinancials[normalized] ?? null);
  const financialsState = $derived(app.stockFinancialsState(normalized));

  const profile = $derived(overview?.profile ?? null);
  const keyStats = $derived(overview?.keyStats ?? null);
  const currency = $derived(overview?.quote.currency ?? overview?.currency ?? "USD");
  const profileSummary = $derived(
    typeof profile?.longBusinessSummary === "string" ? profile.longBusinessSummary : "",
  );

  const financialRows = $derived.by(() => {
    if (!financials) return null;
    const annual = financialPeriod === "annual";
    return {
      income: annual ? financials.incomeAnnual : financials.incomeQuarterly,
      balance: annual ? financials.balanceAnnual : financials.balanceQuarterly,
      cashflow: annual ? financials.cashflowAnnual : financials.cashflowQuarterly,
    };
  });

  $effect(() => {
    if (normalized && normalized !== lastSymbol) {
      lastSymbol = normalized;
      chartRange = "1y";
      financialsLoaded = false;
      void app.loadStock(normalized);
    }
  });

  $effect(() => {
    if (normalized) void app.loadStockChart(normalized, chartRange);
  });

  function loadFinancials() {
    financialsLoaded = true;
    void app.loadStockFinancials(normalized);
  }

  function retryOverview() {
    void app.loadStockOverview(normalized, { force: true });
  }

  function retryChart() {
    void app.loadStockChart(normalized, chartRange, { force: true });
  }

  function value(row: Record<string, unknown> | null, key: string): unknown {
    return row?.[key] ?? null;
  }
</script>

<div class="view-stock">
  <div class="list-topbar">
    <button class="breadcrumb-btn" onclick={() => app.showHome()}>
      <ArrowLeft class="icon" aria-hidden="true" /> Home
    </button>
    <span class="updated-label">
      {overview ? `Updated: ${app.stockUpdatedAt[`overview:${normalized}`] ?? ""}` : ""}
    </span>
  </div>

  {#if overviewState?.status === "loading" && !overview}
    <div class="status-bar s-load">
      <div class="spinner" style:display="block"></div>
      <span class="status-text">Loading {normalized}</span>
    </div>
  {:else if overviewState?.status === "error" && !overview}
    <div class="status-bar s-err">
      <span class="status-text">
        {overviewState.message ?? "Failed to load stock"}
        <button class="retry-btn" onclick={retryOverview}>Retry</button>
      </span>
    </div>
  {:else if overview}
    <StockHeader overview={overview} canAdd={auth.isAdmin} onAdd={() => (addModalOpen = true)} />

    <section class="stock-section">
      <div class="home-section-title">Chart</div>
      {#if chartState?.status === "error" && !chart}
        <div class="status-bar s-err">
          <span class="status-text">
            {chartState.message ?? "Failed to load chart"}
            <button class="retry-btn" onclick={retryChart}>Retry</button>
          </span>
        </div>
      {:else}
        <StockChart data={chart} range={chartRange} onRangeChange={(range) => (chartRange = range)} />
      {/if}
    </section>

    <section class="stock-section stock-two-col">
      <div>
        <div class="home-section-title">Overview</div>
        {#if !overview.fundamentalsAvailable}
          <div class="panel-note">Fundamentals are unavailable right now.</div>
        {/if}
        {#if profileSummary}
          <p class="stock-profile">{profileSummary}</p>
        {/if}
        <div class="table-wrap stock-table-wrap">
          <table aria-label={`${normalized} key statistics`}>
            <tbody>
              <tr><th>Sector</th><td>{String(value(profile, "sector") ?? "—")}</td></tr>
              <tr><th>Industry</th><td>{String(value(profile, "industry") ?? "—")}</td></tr>
              <tr><th>Employees</th><td class="mono">{formatLargeNumber(value(profile, "fullTimeEmployees") as number | null)}</td></tr>
              <tr><th>Beta</th><td class="mono">{formatNumber(value(keyStats, "beta") as number | null)}</td></tr>
              <tr><th>Shares Out</th><td class="mono">{formatLargeNumber(value(keyStats, "sharesOutstanding") as number | null)}</td></tr>
              <tr><th>Book Value</th><td class="mono">{formatMoney(value(keyStats, "bookValue") as number | null, currency)}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div>
        <div class="home-section-title">Technicals</div>
        <TechnicalsPanel technicals={chart?.technicals ?? {}} />
      </div>
    </section>

    <section class="stock-section">
      <div class="stock-section-head">
        <div class="home-section-title">Fundamentals</div>
        <div class="btn-group">
          <button class={financialPeriod === "annual" ? "a-blue" : ""} onclick={() => (financialPeriod = "annual")}>
            Annual
          </button>
          <button class={financialPeriod === "quarterly" ? "a-blue" : ""} onclick={() => (financialPeriod = "quarterly")}>
            Quarterly
          </button>
        </div>
      </div>
      {#if !financialsLoaded}
        <button class="edit-tickers-btn" onclick={loadFinancials}>Load Statements</button>
      {:else if financialsState?.status === "loading" && !financials}
        <div class="status-bar s-load">
          <div class="spinner" style:display="block"></div>
          <span class="status-text">Loading statements</span>
        </div>
      {:else if financialsState?.status === "error" && !financials}
        <div class="status-bar s-err">
          <span class="status-text">
            {financialsState.message ?? "Failed to load statements"}
            <button class="retry-btn" onclick={() => app.loadStockFinancials(normalized, { force: true })}>
              Retry
            </button>
          </span>
        </div>
      {:else if financials && !financials.financialsAvailable}
        <div class="panel-note">Statement data is unavailable right now.</div>
      {:else if financialRows}
        <div class="financials-grid">
          <FinancialsTable caption={`${normalized} income statement`} rows={financialRows.income} />
          <FinancialsTable caption={`${normalized} balance sheet`} rows={financialRows.balance} />
          <FinancialsTable caption={`${normalized} cash flow`} rows={financialRows.cashflow} />
        </div>
      {/if}
    </section>

    <section class="stock-section stock-two-col">
      <div>
        <div class="home-section-title">News</div>
        {#if newsState?.status === "error" && news.length === 0}
          <div class="status-bar s-err">
            <span class="status-text">{newsState.message ?? "Failed to load news"}</span>
          </div>
        {:else}
          <NewsList {news} />
        {/if}
      </div>
      <div>
        <div class="home-section-title">Analyst</div>
        <AnalystPanel {overview} />
      </div>
    </section>
  {/if}
</div>

{#if addModalOpen && overview}
  <AddToWatchlistModal quote={overview.quote} onClose={() => (addModalOpen = false)} />
{/if}
