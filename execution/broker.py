"""下單引擎抽象介面。

策略層不直接碰 broker — 所有訂單必須經過 risk.manager 審核後才送到這裡。
未來接 Alpaca(美股)時只需新增一個實作,策略與風控層不變。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str            # "buy" / "sell"
    amount: float        # 基礎資產數量(如 BTC)
    filled: float
    avg_price: float | None
    status: str          # "closed" / "open" / "canceled" ...
    raw: dict


class Broker(ABC):
    @abstractmethod
    def get_balance(self, asset: str) -> float:
        """回傳某資產的可用餘額。"""

    @abstractmethod
    def get_price(self, symbol: str) -> float:
        """回傳最新成交價。"""

    @abstractmethod
    def market_order(self, symbol: str, side: str, amount: float) -> OrderResult:
        """市價單。amount 為基礎資產數量。"""

    @abstractmethod
    def limit_order(
        self, symbol: str, side: str, amount: float, price: float
    ) -> OrderResult:
        """限價單。"""

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> None: ...
