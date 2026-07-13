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


# 分鐘級抓取範圍(受 Yahoo 限制:分鐘級最多 60 天、1h 最多 730 天)
INTRADAY_PERIOD = {"5m": "5d", "15m": "1mo", "30m": "1mo",
                   "1h": "3mo", "4h": "6mo"}


def resample_4h(df: pd.DataFrame) -> pd.DataFrame:
    """1h → 4h 合成(Yahoo 無原生 4h)。休市空檔不補棒、尾端未滿 4 根保留。"""
    out = df.resample("4h").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    })
    return out.dropna(subset=["open"])


def fetch_intraday(ticker: str, interval: str) -> pd.DataFrame:
    """分鐘/小時級 K 線。index 一律 UTC;4h 由 1h 重採樣。"""
    if interval not in INTRADAY_PERIOD:
        raise ValueError(f"不支援的 interval: {interval}")
    df = yf.download(
        ticker,
        period=INTRADAY_PERIOD[interval],
        interval="1h" if interval == "4h" else interval,
        progress=False,
        auto_adjust=True,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "timestamp"
    return resample_4h(df) if interval == "4h" else df


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
