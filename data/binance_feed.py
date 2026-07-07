"""幣安歷史 K 線抓取(使用公開行情 API,不需要 API key)。"""

from __future__ import annotations

from pathlib import Path

import ccxt
import pandas as pd

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"


def fetch_ohlcv(
    symbol: str,
    timeframe: str = "1d",
    since: str = "2024-07-01",
    exchange: ccxt.Exchange | None = None,
) -> pd.DataFrame:
    """抓取指定交易對的 OHLCV,自動分頁直到最新一根 K 線。"""
    ex = exchange or ccxt.binance()
    since_ms = ex.parse8601(f"{since}T00:00:00Z")
    all_rows: list[list] = []

    while True:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=1000)
        if not batch:
            break
        all_rows.extend(batch)
        # 下一頁從最後一根 K 線之後開始
        last_ts = batch[-1][0]
        if last_ts == since_ms or len(batch) < 1000:
            break
        since_ms = last_ts + 1

    df = pd.DataFrame(
        all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp").set_index("timestamp").sort_index()
    return df


def save(df: pd.DataFrame, symbol: str, timeframe: str) -> Path:
    STORAGE_DIR.mkdir(exist_ok=True)
    path = STORAGE_DIR / f"{symbol.replace('/', '_')}_{timeframe}.parquet"
    df.to_parquet(path)
    return path


def load(symbol: str, timeframe: str = "1d") -> pd.DataFrame:
    path = STORAGE_DIR / f"{symbol.replace('/', '_')}_{timeframe}.parquet"
    return pd.read_parquet(path)
