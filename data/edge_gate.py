"""驗證閘門:每檔候選人的 Donchian edge 每日驗證。

規則(與歷次驗證同一標準):
  標的完整歷史(2000 起或上市日)× Donchian 21 組鄰域(40-70 × 15/20/25)
  vs B&H,Sharpe 年化 252 日,含費用。過半數鄰域勝 = 通過。
結果緩存於 storage/edge_verdicts.json,每日刷新一次。
用途:盤前簡報只對通過者給進場框架;未通過者僅作論點追蹤。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

CACHE_PATH = Path(__file__).resolve().parent.parent / "storage" / "edge_verdicts.json"
GRID = [(e, x) for e in (40, 45, 50, 55, 60, 65, 70) for x in (15, 20, 25)]
FEE, SLIP = 0.001, 0.0005
DAYS = 252


def _donchian_returns(close: pd.Series, entry_n: int, exit_n: int) -> pd.Series:
    upper = close.rolling(entry_n).max().shift(1)
    lower = close.rolling(exit_n).min().shift(1)
    raw = pd.Series(float("nan"), index=close.index)
    raw[close > upper] = 1.0
    raw[close < lower] = 0.0
    pos = raw.ffill().fillna(0.0).shift(1).fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.iloc[0])
    return pos * close.pct_change().fillna(0.0) - turnover * (FEE + SLIP)


def _sharpe(rets: pd.Series) -> float:
    return float(rets.mean() / rets.std() * np.sqrt(DAYS)) if rets.std() else 0.0


def validate(ticker: str) -> dict:
    df = yf.download(ticker, start="2000-01-01", progress=False, auto_adjust=True)
    close = df["Close"][ticker] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
    close = close.dropna()
    bh_sharpe = _sharpe(close.pct_change().fillna(0.0))
    wins = sum(
        _sharpe(_donchian_returns(close, e, x)) > bh_sharpe for e, x in GRID)
    return {
        "wins": int(wins),
        "total": len(GRID),
        "passed": bool(wins > len(GRID) / 2),
        "bh_sharpe": round(bh_sharpe, 2),
        "history_start": close.index[0].strftime("%Y-%m-%d"),
        "date": date.today().isoformat(),
    }


def get_verdicts(tickers: list[str]) -> dict[str, dict]:
    """回傳 {ticker: verdict},當日已驗過的用緩存,否則重跑。"""
    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text())
    today = date.today().isoformat()

    out = {}
    for t in tickers:
        hit = cache.get(t)
        if hit and hit.get("date") == today:
            out[t] = hit
            continue
        try:
            out[t] = validate(t)
        except Exception:
            if hit:  # 今日驗證失敗 → 沿用舊結果,不留空
                out[t] = hit
    cache.update(out)
    CACHE_PATH.parent.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    return out
