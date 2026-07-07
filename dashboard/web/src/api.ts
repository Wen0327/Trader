const BASE = "http://localhost:8787";

/** 任意時間戳 → "YYYY-MM-DD HH:mm:ss"。
 *  支援 log 格式 "…16:00:50,272" 與 ISO "…T13:00:52.123456+00:00"。 */
export const fmtTs = (ts: string | null | undefined) => {
  const m = ts?.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  return m ? `${m[1]} ${m[2]}` : ts ?? "—";
};

export type Status = {
  equity: number | null;
  kill_switch: boolean | null;
  updated_at: string | null;
  positions: Record<string, { amount: number; entry_price: number }>;
  risk_state: { day?: string; day_start_equity?: number; killed?: boolean };
};

export type EquityPoint = { ts: string; equity: number };

export type Trade = {
  ts: string;
  symbol: string;
  side: "buy" | "sell";
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

export type Scan = {
  scanned_at: string;
  movers: Mover[];
  crypto_sentiment?: Record<string, number | null>;
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
export const fetchScan = () => get<Scan>("/api/scan");
export const fetchBacktest = (symbol: string) =>
  get<Backtest>(`/api/backtest?symbol=${encodeURIComponent(symbol)}`);
