const BASE = "http://localhost:8787";

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

export type TrackStatus = {
  equity: number | null;
  kill_switch: boolean | null;
  updated_at: string | null;
  positions: Record<string, { amount: number; entry_price: number }>;
  risk_state: { day?: string; day_start_equity?: number; killed?: boolean };
};

export type Status = TrackStatus & { futures: TrackStatus };

export type EquityPoint = { ts: string; equity: number };

export type Trade = {
  ts: string;
  track: "spot" | "futures";
  symbol: string;
  side: "buy" | "sell" | "short" | "cover";
  amount: number;
  price: number;
  pnl_pct: number | null;
};

export type Mover = {
  rank: number;
  symbol: string;
  price: number;
  change_pct: number;
  quote_volume_usdt: number;
  sentiment?: number | null;
  headlines?: string[];
};

export type RotationRatio = {
  pair: string;
  ratio: number;
  rotation_on: boolean;
  pct_vs_ma200: number;
};

export type WatchItem = {
  ticker: string;
  label: string;
  price: number;
  above_ma200: boolean;
  pct_vs_ma200: number;
  pct_to_55d_high: number;
  status?: "watching" | "near_gate1" | "gate1_passed" | "near_trigger" | "triggered";
  status_label?: string;
  status_rank?: number;
  last_trigger_date?: string | null;
  days_since_trigger?: number | null;
  signal_grade?: "strong" | "mid" | "weak";
  pct_to_exit?: number;
  since_entry_pct?: number;
  entry_date?: string | null;
  bar?: {
    body_pct: number;
    close_pos: number;
    vol_mult: number;
    up: boolean;
    patterns: string[];
  };
};

export type Scan = {
  scanned_at: string;
  movers: Mover[];
  crypto_sentiment?: Record<string, number | null>;
  fear_greed?: { value: number; label: string } | null;
  rotation?: { ratios: RotationRatio[]; watchlist: WatchItem[] };
};

export type Backtest = {
  symbol: string;
  metrics: Record<string, number>;
  n_trades: number;
  curve: { date: string; strategy: number; benchmark: number }[];
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

export type FearGreed = { value: number | null; label: string | null };

export const fetchStatus = () => get<Status>("/api/status");
export const fetchFng = () => get<FearGreed>("/api/fng");
export const fetchEquity = () => get<EquityPoint[]>("/api/equity");
export const fetchTrades = () => get<Trade[]>("/api/trades");
export type RatioHistory = {
  pair: string;
  rotation_on: boolean;
  history: { date: string; ratio: number; ma200: number | null }[];
};

export type Rotation = {
  ratios: RatioHistory[];
  watchlist: WatchItem[];
};

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
  passed: boolean;          // 舊殖利率三關(保留於數據,不再作為主標記)
  momentum_pct?: number | null;
  picked?: boolean;         // ✅ = 動量 TOP10 成員
  range_pos_20d?: number;   // 20日區間位置 0~100
  zone?: "pullback" | "mid" | "high";
  tier?: 1 | 2;             // 美股池分層:1 精華 / 2 二線
  sector?: string;          // 板塊類別
};

export type MomentumPick = {
  ticker: string;
  name: string;
  momentum_pct: number;
  price: number;
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
    picks: MomentumPick[];
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
};

export type UsScreenReport = {
  scanned_at: string;
  universe_size: number;
  fetched: number;
  rows: ValueRow[];
  spy_state: {
    regime_on: boolean;
    pct_vs_ma200: number;
    heat_12m_pct: number;
  } | null;
};

export type Quotes = {
  asof: string;
  quotes: Record<string, { price: number; today_pct: number }>;
};

export const fetchScan = () => get<Scan>("/api/scan");
export const fetchValueScreen = () => get<ValueScreenReport>("/api/value-screen");
export const fetchUsScreen = () => get<UsScreenReport>("/api/us-screen");
export const fetchQuotes = (market: "us" | "tw") =>
  get<Quotes>(`/api/quotes?market=${market}`);
export const fetchRotation = () => get<Rotation>("/api/rotation");
export const fetchRotationTicker = (symbol: string) =>
  get<TickerSeries>(`/api/rotation/ticker?symbol=${encodeURIComponent(symbol)}`);
export const fetchChart = (symbol: string) =>
  get<TickerSeries>(`/api/chart?symbol=${encodeURIComponent(symbol)}`);
export const fetchBacktest = (symbol: string) =>
  get<Backtest>(`/api/backtest?symbol=${encodeURIComponent(symbol)}`);
