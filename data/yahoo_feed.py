"""Yahoo Finance 日線抓取:bStocks 的代理訊號源。

bStocks 歷史太短(2026-06 上市),長均線策略的訊號改用對應正股
(如 QQQB → QQQ)計算,執行仍在幣安。回傳格式與 binance_feed 一致。
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_ohlcv(ticker: str, lookback_days: int = 400) -> pd.DataFrame:
    df = yf.download(
        ticker,
        period=f"{lookback_days}d",
        progress=False,
        auto_adjust=True,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "timestamp"
    return df
