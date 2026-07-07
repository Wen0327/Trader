"""策略基底類別:所有策略只做一件事 — 從 OHLCV 產生目標倉位訊號。

訊號定義:每根 K 線收盤時的目標倉位(1 = 全倉持有, 0 = 空手)。
回測引擎會把訊號延遲一根 K 線執行,避免前視偏差。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """回傳與 ohlcv 同索引的目標倉位序列(0 或 1)。"""
        ...
