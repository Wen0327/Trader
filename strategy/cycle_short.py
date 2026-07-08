"""週期擇時空單策略(S3 修正版)。

規則(全部 a priori,驗證見 scripts/validate_cycle_short.py 與 2026-07-08 會話):
  開空:同時滿足
    1. 處於減半後第 18~30 個月的週期熊市窗口
    2. 收盤跌破 55 日低(Donchian 突破)
    3. 尚未跌破 365 日峰值的 50%(跌夠一半 = 這輪熊市視為打完,不再開空)
  回補:突破 20 日高(止損)或 跌破 50% 地板(獲利目標)

驗證紀錄:2018-02 起 BTC Sharpe 0.93→1.10、ETH 0.82→0.90,
參數鄰域 30/30 全勝。已知弱點:熊市片段 n≈3,置信度先天受限,
故僅限合約 testnet 紙上驗證,2026-10 窗口結束覆盤。

回傳訊號:-1(持空)/ 0(空手)。此策略不做多。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.base import Strategy

HALVINGS = [
    pd.Timestamp("2016-07-09", tz="UTC"),
    pd.Timestamp("2020-05-11", tz="UTC"),
    pd.Timestamp("2024-04-20", tz="UTC"),
]


class CycleShort(Strategy):
    def __init__(self, entry_n: int = 55, exit_n: int = 20,
                 window_months: tuple[int, int] = (18, 30), floor: float = 0.5):
        self.entry_n = entry_n
        self.exit_n = exit_n
        self.window_months = window_months
        self.floor = floor
        self.name = f"cycle_short_{entry_n}_{exit_n}"

    def _in_window(self, index: pd.DatetimeIndex) -> np.ndarray:
        m0, m1 = self.window_months
        mask = np.zeros(len(index), dtype=bool)
        for h in HALVINGS:
            mask |= (index >= h + pd.DateOffset(months=m0)) & (
                index < h + pd.DateOffset(months=m1))
        return mask

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        close = ohlcv["close"]
        lo55 = close.rolling(self.entry_n).min().shift(1)
        hi20 = close.rolling(self.exit_n).max().shift(1)
        peak = close.rolling(365, min_periods=100).max().shift(1)
        window = self._in_window(close.index)

        pos = np.zeros(len(close))
        holding = 0.0
        for i in range(len(close)):
            c = close.iloc[i]
            if np.isnan(lo55.iloc[i]):
                pos[i] = holding
                continue
            level = peak.iloc[i] * self.floor if not np.isnan(peak.iloc[i]) else np.nan
            if holding == -1 and (c > hi20.iloc[i] or (not np.isnan(level) and c < level)):
                holding = 0.0
            if holding == 0 and window[i] and c < lo55.iloc[i] \
                    and not np.isnan(level) and c > level:
                holding = -1.0
            pos[i] = holding
        return pd.Series(pos, index=close.index)
