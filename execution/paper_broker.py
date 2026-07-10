"""紙上撮合引擎:testnet 不支援的標的(如 bStocks)自製模擬交易。

成交規則:市價單按注入的即時價 ± 滑價成交,收手續費;
虛擬資金,現金水位自行記帳(狀態由呼叫方的 Portfolio 管理持倉,
本 broker 只管現金與成交)。價格來源 = 幣安公開行情(真實執行場所)。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Callable

from execution.broker import Broker, OrderResult

FEE = 0.001
SLIPPAGE = 0.0005
INITIAL_CASH = 10_000.0

CASH_PATH = Path(__file__).resolve().parent.parent / "storage" / "paper_cash.json"


class PaperBroker(Broker):
    def __init__(self, price_func: Callable[[str], float],
                 cash_path: Path = CASH_PATH):
        self._price = price_func
        self._cash_path = cash_path
        if cash_path.exists():
            self._cash = float(json.loads(cash_path.read_text())["cash"])
        else:
            self._cash = INITIAL_CASH
            self._save()

    def _save(self) -> None:
        self._cash_path.parent.mkdir(exist_ok=True)
        self._cash_path.write_text(json.dumps({"cash": round(self._cash, 2)}))

    def get_balance(self, asset: str) -> float:
        return self._cash  # 單一計價資產(USDT)

    def get_price(self, symbol: str) -> float:
        return self._price(symbol)

    def market_order(self, symbol: str, side: str, amount: float) -> OrderResult:
        mid = self._price(symbol)
        fill = mid * (1 + SLIPPAGE) if side == "buy" else mid * (1 - SLIPPAGE)
        gross = fill * amount
        fee = gross * FEE
        if side == "buy":
            cost = gross + fee
            if cost > self._cash + 1e-9:
                raise RuntimeError(f"紙上資金不足: 需 {cost:.2f}, 有 {self._cash:.2f}")
            self._cash -= cost
        else:
            self._cash += gross - fee
        self._save()
        return OrderResult(
            order_id=f"paper-{uuid.uuid4().hex[:8]}",
            symbol=symbol, side=side, amount=amount,
            filled=amount, avg_price=round(fill, 4),
            status="closed", raw={"fee": round(fee, 4)},
        )

    def limit_order(self, symbol: str, side: str, amount: float, price: float) -> OrderResult:
        raise NotImplementedError("紙上引擎只支援市價單")

    def cancel_order(self, order_id: str, symbol: str) -> None:
        pass  # 市價單即時成交,無單可撤

    def amount_to_precision(self, symbol: str, amount: float) -> float:
        import math
        return math.floor(amount * 1e5) / 1e5  # 無條件捨去,與交易所行為一致
