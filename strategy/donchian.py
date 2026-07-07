"""Donchian 通道突破(海龜經典參數 55/20)。

收盤突破前 entry_n 日高 → 做多;跌破前 exit_n 日低 → 出場。
驗證紀錄(樣本外 2019-09~2025-08,scripts/validate_alternatives.py):
- BTC: Sharpe 1.10 vs B&H 0.96,MaxDD -39% vs -77%,鄰近參數 21/21 勝
- ETH: Sharpe 1.19 vs B&H 1.07(鄰近參數僅 8/21 勝 → 視為打平),MaxDD 減半
"""

from __future__ import annotations

import pandas as pd

from strategy.base import Strategy


class DonchianBreakout(Strategy):
    def __init__(self, entry_n: int = 55, exit_n: int = 20):
        self.entry_n = entry_n
        self.exit_n = exit_n
        self.name = f"donchian_{entry_n}_{exit_n}"

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        close = ohlcv["close"]
        upper = close.rolling(self.entry_n).max().shift(1)
        lower = close.rolling(self.exit_n).min().shift(1)
        raw = pd.Series(float("nan"), index=close.index)
        raw[close > upper] = 1.0
        raw[close < lower] = 0.0
        return raw.ffill().fillna(0.0)
