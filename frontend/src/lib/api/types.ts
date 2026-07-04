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
