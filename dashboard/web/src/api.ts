const BASE = "http://localhost:8787";

/** 任意時間戳 → "YYYY-MM-DD HH:mm:ss"。
 *  支援 log 格式 "…16:00:50,272" 與 ISO "…T13:00:52.123456+00:00"。 */
export const fmtTs = (ts: string | null | undefined) => {
  const m = ts?.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  return m ? `${m[1]} ${m[2]}` : ts ?? "—";
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
  series: { date: string; close: number; ma200: number | null; hi55: number | null }[];
};

export const fetchScan = () => get<Scan>("/api/scan");
export const fetchRotation = () => get<Rotation>("/api/rotation");
export const fetchRotationTicker = (symbol: string) =>
  get<TickerSeries>(`/api/rotation/ticker?symbol=${encodeURIComponent(symbol)}`);
export const fetchBacktest = (symbol: string) =>
  get<Backtest>(`/api/backtest?symbol=${encodeURIComponent(symbol)}`);
