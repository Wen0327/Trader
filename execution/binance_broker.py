"""幣安現貨 broker(ccxt 實作,支援 testnet / 正式環境切換)。"""

from __future__ import annotations

import os
from pathlib import Path

import ccxt
from dotenv import load_dotenv

from execution.broker import Broker, OrderResult

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class BinanceBroker(Broker):
    def __init__(self, testnet: bool = True):
        """預設 testnet。要連正式環境必須明確傳 testnet=False。"""
        prefix = "BINANCE_TESTNET" if testnet else "BINANCE"
        api_key = os.environ.get(f"{prefix}_API_KEY", "")
        api_secret = os.environ.get(f"{prefix}_API_SECRET", "")
        if not api_key or not api_secret:
            raise RuntimeError(f".env 缺少 {prefix}_API_KEY / {prefix}_API_SECRET")

        self.testnet = testnet
        self._ex = ccxt.binance({"apiKey": api_key, "secret": api_secret})
        if testnet:
            self._ex.set_sandbox_mode(True)
        self._ex.load_markets()

    def get_balance(self, asset: str) -> float:
        balance = self._ex.fetch_balance()
        return float(balance.get("free", {}).get(asset, 0.0) or 0.0)

    def get_price(self, symbol: str) -> float:
        return float(self._ex.fetch_ticker(symbol)["last"])

    def market_order(self, symbol: str, side: str, amount: float) -> OrderResult:
        order = self._ex.create_order(symbol, "market", side, amount)
        return self._to_result(order, symbol)

    def limit_order(
        self, symbol: str, side: str, amount: float, price: float
    ) -> OrderResult:
        order = self._ex.create_order(symbol, "limit", side, amount, price)
        return self._to_result(order, symbol)

    def cancel_order(self, order_id: str, symbol: str) -> None:
        self._ex.cancel_order(order_id, symbol)

    def _to_result(self, order: dict, symbol: str) -> OrderResult:
        # 市價單回應可能不含均價,補查一次訂單狀態
        if order.get("average") is None and order.get("id"):
            try:
                order = self._ex.fetch_order(order["id"], symbol)
            except Exception:
                pass
        return OrderResult(
            order_id=str(order.get("id", "")),
            symbol=symbol,
            side=str(order.get("side", "")),
            amount=float(order.get("amount") or 0.0),
            filled=float(order.get("filled") or 0.0),
            avg_price=float(order["average"]) if order.get("average") else None,
            status=str(order.get("status", "unknown")),
            raw=order,
        )
