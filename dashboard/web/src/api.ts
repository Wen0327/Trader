// dev:Vite 開發伺服器(5173)跨到 API(8787);prod:同源相對路徑(API serve 前端)
const BASE = import.meta.env.DEV ? "http://localhost:8787" : "";

/** API 時間戳(一律 UTC)→ 本地時間 "YYYY-MM-DD HH:mm:ss" 顯示。
 *  支援 "YYYY-MM-DD HH:mm:ss" 與 ISO 格式。 */
export const fmtTs = (ts: string | null | undefined) => {
  const m = ts?.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  if (!m) return ts ?? "—";
  const d = new Date(`${m[1]}T${m[2]}Z`); // API 慣例:無時區標記即 UTC
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
         `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};

export type EquityPoint = { ts: string; equity: number };

export class UnauthorizedError extends Error {}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: "include" });
  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

export const fetchMe = () => get<{ email: string }>("/auth/me");
export const requestLogin = async (email: string) => {
  const res = await fetch(`${BASE}/auth/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email }),
  });
  return res.json();
};
export const logout = () =>
  fetch(`${BASE}/auth/logout`, { method: "POST", credentials: "include" });

export type TickerSeries = {
  ticker: string;
  label: string;
  series: {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    ma200: number | null;
    hi55: number | null;
    lo20: number | null;
    breakout: boolean;
  }[];
};

export type ValueRow = {
  ticker: string;
  name: string;
  price: number;
  dividend_yield: number | null;
  revenue_growth: number | null;
  profit_margin: number | null;
  pe: number | null;
  debt_to_equity: number | null;
  passed: boolean;
  momentum_pct?: number | null;
  picked?: boolean;
  range_pos_20d?: number;
  zone?: "pullback" | "mid" | "high";
};

export type ValueScreenReport = {
  scanned_at: string;
  criteria: {
    min_dividend_yield: number;
    min_revenue_growth: number;
    min_profit_margin: number;
  };
  universe_size: number;
  fetched: number;
  rows: ValueRow[];
  momentum?: {
    picks: { ticker: string; name: string; momentum_pct: number; price: number }[];
    rebalanced: boolean;
    performance: {
      since: string;
      n_rebalances: number;
      strategy_pct: number;
      bench_0050_pct: number;
    } | null;
  };
  market_state?: {
    regime_on: boolean;
    pct_vs_ma200: number;
    heat_12m_pct: number;
    bucket: string;
    bucket_next_q_avg: number;
    bucket_win_rate: number;
    regime_next_q_avg: number;
    regime_win_rate: number;
  };
  paper?: {
    equity: number;
    cash: number;
    started: string | null;
    return_pct: number;
    n_trades: number;
    holdings: {
      ticker: string; name: string; shares: number;
      entry_price: number; price: number; pnl_pct: number;
    }[];
  };
};

export type Quotes = {
  asof: string;
  quotes: Record<string, { price: number; today_pct: number }>;
};

export type PaperBooksReport = {
  us: unknown;
  us_stocks: unknown;
  tw: {
    summary: NonNullable<ValueScreenReport["paper"]> | null;
    trades: {
      date: string; side: string; ticker: string; name?: string;
      shares: number; price: number; pnl_pct: number | null; note?: string;
    }[];
    equity_curve: EquityPoint[];
  };
  tw_d: {
    summary: (NonNullable<ValueScreenReport["paper"]> & {
      reserve_cash?: number;
      exp_state?: string;
    }) | null;
    trades: {
      date: string; side: string; ticker: string; name?: string;
      shares: number; price: number; pnl_pct: number | null; note?: string;
    }[];
    equity_curve: EquityPoint[];
  };
};

export type PaperTradeRecord = {
  date: string; side: string; ticker: string; name?: string;
  shares: number; price: number | null; pnl_pct: number | null;
  pnl_amt?: number; note?: string;
};

export type PaperHolding = {
  ticker: string; name: string; shares: number;
  entry_price: number; price: number; pnl_pct: number;
};

export type PaperTradesReport = {
  trades: PaperTradeRecord[];
  holdings: PaperHolding[];
  summary: {
    total_realized_pnl: number;
    total_unrealized_pnl: number;
    n_sells: number;
    n_holdings: number;
    win_rate: number;
    avg_win: number;
    avg_loss: number;
  };
};

export const fetchPaperTrades = (book: "tw" | "tw_d") =>
  get<PaperTradesReport>(`/api/paper/trades?book=${book}`);

export type BrokerStatus = {
  configured: boolean;
  has_ca: boolean;
  mode: "simulation" | "production";
};

export type BrokerPosition = {
  code: string;
  lots: number;
  avg_price: number;
  last_price: number;
  pnl: number;
};

export type BrokerPositionsReport = {
  positions: BrokerPosition[];
  paper_count: number;
  diffs: string[];
};

export const fetchBrokerStatus = () => get<BrokerStatus>("/api/broker/status");
export const fetchBrokerPositions = async () => {
  const res = await fetch(`${BASE}/api/broker/positions`, {
    method: "POST", credentials: "include",
  });
  if (res.status === 401) throw new UnauthorizedError();
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<BrokerPositionsReport>;
};
export const fetchValueScreen = () => get<ValueScreenReport>("/api/value-screen");
export const fetchQuotes = (market: "us" | "tw") =>
  get<Quotes>(`/api/quotes?market=${market}`);
export const fetchPaperBooks = () => get<PaperBooksReport>("/api/paper");
export type ChartInterval = "5m" | "15m" | "30m" | "1h" | "4h" | "1d";
export const fetchChart = (symbol: string, interval: ChartInterval = "1d") =>
  get<TickerSeries>(
    `/api/chart?symbol=${encodeURIComponent(symbol)}&interval=${interval}`);
export const fetchStarred = (market: "us" | "tw") =>
  get<{ tickers: string[] }>(`/api/starred?market=${market}`);
export const saveStarred = async (market: "us" | "tw", tickers: string[]) => {
  await fetch(`${BASE}/api/starred`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ market, tickers }),
  });
};
