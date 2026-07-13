"""Yahoo Finance 日線抓取:bStocks 的代理訊號源。

bStocks 歷史太短(2026-06 上市),長均線策略的訊號改用對應正股
(如 QQQB → QQQ)計算,執行仍在幣安。回傳格式與 binance_feed 一致。
"""

from __future__ import annotations

import time
from typing import Callable

import pandas as pd
import yfinance as yf


def retry_download(fetch: Callable[[], pd.DataFrame],
                   attempts: int = 3, delay_sec: int = 60) -> pd.DataFrame:
    """批量下載全數失敗(整個 DataFrame 無有效值)時重試。

    背景:Yahoo 偶發斷線/限流會讓整批 ticker 一起失敗;週更任務
    crash 就沉默爛一週(2026-07-13 台股週掃事故)。部分失敗屬正常
    (下市、停牌),只有「全空」才視為暫時性故障。
    重試用滿仍全空 → RuntimeError,交由呼叫端通知。
    """
    for i in range(attempts):
        df = fetch()
        if not df.dropna(how="all").empty:
            return df
        if i < attempts - 1:
            time.sleep(delay_sec)
    raise RuntimeError(
        f"Yahoo 批量下載全數失敗(重試 {attempts} 次,間隔 {delay_sec}s)")


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
