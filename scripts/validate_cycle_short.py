"""週期擇時做空驗證:python scripts/validate_cycle_short.py

假設(a priori 固定):
  減半日 2016-07-09 / 2020-05-11 / 2024-04-20(客觀事實)
  週期熊市窗口 = 減半後第 18~30 個月(經典四年週期敘事,不掃描)
  S1: 空單只准在熊市窗口內開(Donchian 55低進 / 20高回補)
  S2: S1 + 近60天內曾出現 F&G>75 才准開空
  多單照常(= 現役)。
警告: 熊市窗口樣本 n≈2-3,結論置信度先天受限,附逐筆空單明細。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data.binance_feed import load
from scripts.validate_fng import fetch_fng_history
from scripts.validate_short import evaluate

HALVINGS = [pd.Timestamp(d, tz="UTC") for d in ("2016-07-09", "2020-05-11", "2024-04-20")]
START = "2018-02-01"


def in_bear_window(index: pd.DatetimeIndex) -> np.ndarray:
    mask = np.zeros(len(index), dtype=bool)
    for h in HALVINGS:
        lo, hi = h + pd.DateOffset(months=18), h + pd.DateOffset(months=30)
        mask |= (index >= lo) & (index < hi)
    return mask


def recent_greed(index: pd.DatetimeIndex, fng: pd.Series, days: int = 60) -> np.ndarray:
    f = fng.reindex(index.normalize()).ffill()
    return (f > 75).rolling(days, min_periods=1).max().fillna(0).to_numpy() > 0


def positions(close: pd.Series, short_allowed: np.ndarray, trades: list, symbol: str,
              variant: str) -> pd.Series:
    hi55 = close.rolling(55).max().shift(1)
    lo20 = close.rolling(20).min().shift(1)
    lo55 = close.rolling(55).min().shift(1)
    hi20 = close.rolling(20).max().shift(1)

    pos = np.zeros(len(close))
    holding, entry_px, entry_dt = 0.0, 0.0, None
    for i in range(len(close)):
        c = close.iloc[i]
        if np.isnan(hi55.iloc[i]):
            pos[i] = holding
            continue
        if holding == 1 and c < lo20.iloc[i]:
            holding = 0.0
        elif holding == -1 and c > hi20.iloc[i]:
            trades.append((variant, symbol, entry_dt.date(), close.index[i].date(),
                           (entry_px / c - 1) * 100))
            holding = 0.0
        if holding == 0:
            if c > hi55.iloc[i]:
                holding = 1.0
            elif c < lo55.iloc[i] and short_allowed[i]:
                holding, entry_px, entry_dt = -1.0, c, close.index[i]
        pos[i] = holding
    if holding == -1:
        trades.append((variant, symbol, entry_dt.date(), "持倉中",
                       (entry_px / close.iloc[-1] - 1) * 100))
    return pd.Series(pos, index=close.index)


if __name__ == "__main__":
    fng = fetch_fng_history()
    trades: list = []
    for symbol in ["BTC/USDT", "ETH/USDT"]:
        close = load(symbol)["close"]
        bear = in_bear_window(close.index)
        greed = recent_greed(close.index, fng)
        variants = {
            "純做多(現役)": np.zeros(len(close), dtype=bool),
            "S1 週期窗口做空": bear,
            "S2 窗口+曾極貪": bear & greed,
        }
        print(f"\n=== {symbol}({START} 起)===")
        print(f"{'變體':<14} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} {'空倉率':>7}")
        for name, allowed in variants.items():
            p = positions(close, allowed, trades, symbol, name)
            s = evaluate(close, p)
            print(f"{name:<14} {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
                  f"{s['sharpe']:>7.2f} {s['short_pct']:>7.1%}")

    print("\n=== 空單逐筆明細 ===")
    print(f"{'變體':<14} {'標的':<10} {'進場':>12} {'出場':>12} {'損益%':>8}")
    for v, sym, ein, eout, pnl in trades:
        print(f"{v:<14} {sym:<10} {str(ein):>12} {str(eout):>12} {pnl:>+7.1f}%")
