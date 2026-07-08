"""幣安 USDT-M 合約 broker(僅 testnet,槓桿硬鎖 1x)。

ccxt 已移除合約 testnet 的內建 sandbox 支援,此處手動覆寫 API 端點
指向 testnet.binancefuture.com(服務仍在營運)。
安全設計:此類別無正式環境模式 — 建構子不接受任何「連實盤」的參數。
"""

from __future__ import annotations

import os
from pathlib import Path

import ccxt
from dotenv import load_dotenv

from execution.broker import Broker, OrderResult

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

LEVERAGE = 1  # 硬鎖,不可配置


class BinanceFuturesTestnetBroker(Broker):
    def __init__(self):
        api_key = os.environ.get("BINANCE_FUTURES_TESTNET_API_KEY", "")
        api_secret = os.environ.get("BINANCE_FUTURES_TESTNET_API_SECRET", "")
        if not api_key or not api_secret:
            raise RuntimeError(".env 缺少 BINANCE_FUTURES_TESTNET_API_KEY/SECRET")

        self._ex = ccxt.binanceusdm({
            "apiKey": api_key,
            "secret": api_secret,
            "options": {"fetchCurrencies": False},
        })
        for k, v in self._ex.urls["api"].items():
            if isinstance(v, str) and "fapi.binance.com" in v:
                self._ex.urls["api"][k] = v.replace(
                    "fapi.binance.com", "testnet.binancefuture.com")
        self._ex.load_markets()
        self._leverage_set: set[str] = set()

    def _ensure_leverage(self, symbol: str) -> None:
        if symbol not in self._leverage_set:
            self._ex.set_leverage(LEVERAGE, symbol)
            self._leverage_set.add(symbol)

    def get_balance(self, asset: str) -> float:
        bal = self._ex.fetch_balance()
        return float(bal.get("total", {}).get(asset, 0.0) or 0.0)

    def get_price(self, symbol: str) -> float:
        return float(self._ex.fetch_ticker(symbol)["last"])

    def market_order(self, symbol: str, side: str, amount: float) -> OrderResult:
        self._ensure_leverage(symbol)
        order = self._ex.create_order(symbol, "market", side, amount)
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

    def limit_order(self, symbol: str, side: str, amount: float, price: float) -> OrderResult:
        raise NotImplementedError("合約軌道目前只用市價單")

    def cancel_order(self, order_id: str, symbol: str) -> None:
        self._ex.cancel_order(order_id, symbol)

    def amount_to_precision(self, symbol: str, amount: float) -> float:
        return float(self._ex.amount_to_precision(symbol, amount))
