"""長均線 Regime 過濾:收盤 > MA(n) 做多,否則空手。

用途:指數型標的(QQQB 等)。單一股票與 crypto 請用各自驗證過的策略。
驗證紀錄(QQQ 2000-2026,scripts/validate_qqq.py):
- Regime200: Sharpe 0.60 vs B&H 0.44,MaxDD -34% vs -83%
- MA 長度鄰域 125-300:8/9 勝 B&H Sharpe(高原確認)
- 同數據 Donchian 僅 1/21 勝 → 通道突破不適用於指數
"""

from __future__ import annotations

import pandas as pd

from strategy.base import Strategy


class RegimeFilter(Strategy):
    def __init__(self, n: int = 200):
        self.n = n
        self.name = f"regime_{n}"

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        close = ohlcv["close"]
        ma = close.rolling(self.n).mean()
        signal = (close > ma).astype(float)
        signal[ma.isna()] = 0.0
        return signal
