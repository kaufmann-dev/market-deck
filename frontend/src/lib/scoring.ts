import type { MetricsResponse, MonthlyCell, TickerMetrics } from "./api/types";

export interface ScoredRow {
  id: number;
  ticker: string;
  name: string;
  tag: string;
  currency: string;
  ok: boolean;
  score: number | null;
  currentPrice: number | null;
  basePrice: number | null;
  baseDate: string | null;
  ret12m: number | null;
  monthly: MonthlyCell[];
  rank: number;
}

function toRow(t: TickerMetrics, lb: number): Omit<ScoredRow, "rank"> {
  const lookback = t.lookbacks[String(lb)] ?? { ret: null, basePrice: null, baseDate: null };
  return {
    id: t.id,
    ticker: t.symbol,
    name: t.name,
    tag: t.tag,
    currency: t.currency,
    ok: t.ok,
    score: lookback.ret,
    currentPrice: t.currentPrice,
    basePrice: lookback.basePrice,
    baseDate: lookback.baseDate,
    ret12m: t.ret12m,
    monthly: t.monthly,
  };
}

/** Rank rows by the selected lookback return: scored rows sorted descending,
 * null-score rows appended after with continuing rank numbers. */
export function rankRows(metrics: MetricsResponse, lb: number, tagFilter: string): ScoredRow[] {
  let rows = metrics.tickers.map((t) => toRow(t, lb));
  if (tagFilter !== "All") {
    rows = rows.filter((row) => row.tag === tagFilter);
  }
  const ranked = rows
    .filter((row) => row.score !== null)
    .sort((a, b) => (b.score as number) - (a.score as number))
    .map((row, index) => ({ ...row, rank: index + 1 }));
  const missing = rows
    .filter((row) => row.score === null)
    .map((row, index) => ({ ...row, rank: ranked.length + index + 1 }));
  return [...ranked, ...missing];
}
