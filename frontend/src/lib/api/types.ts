export interface TagInfo {
  tag: string;
  bg: string;
  text: string;
  border: string;
  sortOrder: number;
}

export interface TickerItem {
  id: number;
  ticker: string;
  name: string;
  tag: string;
  currency: string;
}

export interface ListInfo {
  id: number;
  name: string;
  shortName: string;
  category: string;
  description: string;
  currency: string;
  showTag: boolean;
  tags: TagInfo[];
  items: TickerItem[];
}

export interface InitResponse {
  settings: Record<string, string>;
  lists: Record<string, ListInfo>;
}

export interface LookbackResult {
  ret: number | null;
  basePrice: number | null;
  baseDate: string | null;
}

export interface MonthlyCell {
  label: string;
  ret: number | null;
}

export interface TickerMetrics {
  id: number;
  symbol: string;
  name: string;
  tag: string;
  currency: string;
  ok: boolean;
  currentPrice: number | null;
  lookbacks: Record<string, LookbackResult>;
  ret12m: number | null;
  monthly: MonthlyCell[];
}

export interface MetricsResponse {
  baseCurrency: string;
  asOf: string;
  tickers: TickerMetrics[];
  failed: string[];
}

export interface CurrentUser {
  email?: string;
  role: "admin" | "demo";
}

export interface SearchQuote {
  symbol: string;
  name: string;
  exchange?: string | null;
  quoteType?: string | null;
  type?: string | null;
  currency?: string | null;
}

export interface NewsItem {
  title: string;
  publisher: string;
  link: string;
  publishedAt?: number | null;
  thumbnail?: string | null;
}

export interface SearchResult {
  quotes: SearchQuote[];
  news: NewsItem[];
}

export interface StockQuote {
  symbol: string;
  name: string;
  exchange?: string | null;
  fullExchangeName?: string | null;
  currency?: string | null;
  regularMarketPrice?: number | null;
  previousClose?: number | null;
  dayChange?: number | null;
  dayChangePercent?: number | null;
  marketCap?: number | null;
  trailingPE?: number | null;
  dividendYield?: number | null;
  fiftyTwoWeekHigh?: number | null;
  fiftyTwoWeekLow?: number | null;
  volume?: number | null;
  averageVolume?: number | null;
  targetMeanPrice?: number | null;
}

export type StockProfile = Record<string, unknown>;
export type KeyStats = Record<string, unknown>;
export type FinancialData = Record<string, unknown>;
export type CalendarEvents = Record<string, unknown>;
export type RecommendationTrend = Record<string, unknown>;

export interface StockOverview {
  quote: StockQuote;
  profile: StockProfile | null;
  keyStats: KeyStats | null;
  financialData: FinancialData | null;
  calendar: CalendarEvents | null;
  recommendation: RecommendationTrend | null;
  earnings?: Record<string, unknown> | null;
  earningsTrend?: Record<string, unknown> | null;
  currency?: string | null;
  fundamentalsAvailable: boolean;
}

export interface OhlcPoint {
  date: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close: number;
  volume?: number | null;
}

export interface Technicals {
  sma20?: number | null;
  sma50?: number | null;
  sma200?: number | null;
  ema12?: number | null;
  ema26?: number | null;
  rsi14?: number | null;
  macd?: {
    macd?: number | null;
    signal?: number | null;
    histogram?: number | null;
  };
  fiftyTwoWeekHigh?: number | null;
  fiftyTwoWeekLow?: number | null;
  percentFromHigh?: number | null;
  avgVolume20?: number | null;
  annualizedVolatility?: number | null;
}

export interface ChartResponse {
  ohlc: OhlcPoint[];
  meta: Record<string, unknown>;
  technicals: Technicals;
}

export interface FinancialsResponse {
  financialsAvailable: boolean;
  incomeAnnual: Record<string, unknown>[];
  incomeQuarterly: Record<string, unknown>[];
  balanceAnnual: Record<string, unknown>[];
  balanceQuarterly: Record<string, unknown>[];
  cashflowAnnual: Record<string, unknown>[];
  cashflowQuarterly: Record<string, unknown>[];
}
