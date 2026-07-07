"""基準策略:SMA 均線交叉動量。

快線 > 慢線 → 持有;否則空手。
這是刻意簡單的 baseline,目的是驗證回測流程,不是為了賺錢。
"""

from __future__ import annotations

import pandas as pd

from strategy.base import Strategy


class SmaCross(Strategy):
    def __init__(self, fast: int = 20, slow: int = 60):
        assert fast < slow, "fast 必須小於 slow"
        self.fast = fast
        self.slow = slow
        self.name = f"sma_{fast}_{slow}"

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        close = ohlcv["close"]
        fast_ma = close.rolling(self.fast).mean()
        slow_ma = close.rolling(self.slow).mean()
        signal = (fast_ma > slow_ma).astype(float)
        # 慢線尚未形成前不持倉
        signal[slow_ma.isna()] = 0.0
        return signal
