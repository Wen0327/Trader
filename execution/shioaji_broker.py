"""永豐 Shioaji 台股下單模組。

所有憑證從環境變數讀取,程式碼內不含任何個人資訊:
  SJ_API_KEY, SJ_SECRET_KEY       — SinoTrade API token
  SJ_CA_PATH, SJ_CA_PASSWD        — CA 憑證路徑與密碼(實盤用)
  SJ_PERSON_ID                    — 身分證字號(實盤用)

simulation=True 時不需要 CA,可完整測試下單流程。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

try:
    import shioaji as sj
except ImportError:
    sj = None  # 允許在未安裝 shioaji 的環境 import(測試用 mock）

logger = logging.getLogger(__name__)


class BrokerError(Exception):
    pass


class ShioajiBroker:
    """封裝 Shioaji SDK,只暴露本系統需要的功能。"""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        simulation: bool = True,
        ca_path: str | None = None,
        ca_passwd: str | None = None,
        person_id: str | None = None,
    ):
        if sj is None:
            raise BrokerError("shioaji 未安裝,請執行 pip install shioaji")
        self.simulation = simulation
        self.api: sj.Shioaji = sj.Shioaji(simulation=simulation)
        self.api.login(api_key=api_key, secret_key=secret_key)

        if not simulation:
            if not all([ca_path, ca_passwd, person_id]):
                raise BrokerError(
                    "實盤模式需要 CA 憑證(SJ_CA_PATH / SJ_CA_PASSWD / SJ_PERSON_ID)"
                )
            self.api.activate_ca(
                ca_path=ca_path,
                ca_passwd=ca_passwd,
                person_id=person_id,
            )

    # ── 下單 ─────────────────────────────────────────────

    def _resolve_contract(self, ticker: str):
        """代號轉 Shioaji contract。接受 '2330' 或 '2330.TW' 格式。"""
        code = ticker.replace(".TW", "").replace(".TWO", "")
        contract = self.api.contracts.get(code)
        if contract is None:
            raise BrokerError(f"找不到標的:{ticker}")
        return contract

    def buy(self, ticker: str, price: float, lots: int) -> object:
        contract = self._resolve_contract(ticker)
        order = sj.StockOrder(
            action=sj.Action.Buy,
            price=round(price, 2),
            quantity=lots,
            price_type=sj.StockPriceType.LMT,
            order_type=sj.OrderType.ROD,
            order_lot=sj.StockOrderLot.Common,
            order_cond=sj.StockOrderCond.Cash,
            account=self.api.stock_account,
        )
        trade = self.api.place_order(contract, order)
        logger.info("買入 %s %d張 @ %.2f (sim=%s)", ticker, lots, price, self.simulation)
        return trade

    def sell(self, ticker: str, price: float, lots: int) -> object:
        contract = self._resolve_contract(ticker)
        order = sj.StockOrder(
            action=sj.Action.Sell,
            price=round(price, 2),
            quantity=lots,
            price_type=sj.StockPriceType.LMT,
            order_type=sj.OrderType.ROD,
            order_lot=sj.StockOrderLot.Common,
            order_cond=sj.StockOrderCond.Cash,
            account=self.api.stock_account,
        )
        trade = self.api.place_order(contract, order)
        logger.info("賣出 %s %d張 @ %.2f (sim=%s)", ticker, lots, price, self.simulation)
        return trade

    # ── 零股下單 ─────────────────────────────────────────

    def buy_odd(self, ticker: str, price: float, shares: int) -> object:
        """零股買入(1–999 股)。"""
        contract = self._resolve_contract(ticker)
        order = sj.StockOrder(
            action=sj.Action.Buy,
            price=round(price, 2),
            quantity=shares,
            price_type=sj.StockPriceType.LMT,
            order_type=sj.OrderType.ROD,
            order_lot=sj.StockOrderLot.Odd,
            order_cond=sj.StockOrderCond.Cash,
            account=self.api.stock_account,
        )
        trade = self.api.place_order(contract, order)
        logger.info("零股買入 %s %d股 @ %.2f (sim=%s)", ticker, shares, price, self.simulation)
        return trade

    def sell_odd(self, ticker: str, price: float, shares: int) -> object:
        """零股賣出(1–999 股)。"""
        contract = self._resolve_contract(ticker)
        order = sj.StockOrder(
            action=sj.Action.Sell,
            price=round(price, 2),
            quantity=shares,
            price_type=sj.StockPriceType.LMT,
            order_type=sj.OrderType.ROD,
            order_lot=sj.StockOrderLot.Odd,
            order_cond=sj.StockOrderCond.Cash,
            account=self.api.stock_account,
        )
        trade = self.api.place_order(contract, order)
        logger.info("零股賣出 %s %d股 @ %.2f (sim=%s)", ticker, shares, price, self.simulation)
        return trade

    # ── 持倉查詢 ─────────────────────────────────────────

    def positions(self) -> dict[str, dict]:
        """回傳持倉 dict: {code: {lots, avg_price, last_price, pnl}}。"""
        raw = self.api.list_positions(account=self.api.stock_account)
        return {
            p.code: {
                "lots": p.quantity,
                "avg_price": float(p.avg_price),
                "last_price": float(p.last_price),
                "pnl": float(p.pnl),
            }
            for p in raw
        }

    # ── 清理 ─────────────────────────────────────────────

    def logout(self) -> None:
        self.api.logout()


def reconcile(
    broker_pos: dict[str, dict],
    paper_pos: dict[str, dict],
) -> list[str]:
    """比對券商持倉 vs 紙上帳本,回傳差異清單。

    broker_pos: {code: {lots, avg_price}} — 來自 ShioajiBroker.positions()
    paper_pos:  {ticker: {shares, entry_price}} — 來自 tw_paper_state.json['positions']

    代號對應: paper 用 '2330.TW',broker 用 '2330'。
    單位對應: paper 用 shares(股),broker 用 lots(張 = 1000 股)。
    """
    diffs: list[str] = []

    # 把 paper 代號轉成 broker 格式
    paper_mapped = {
        t.replace(".TW", "").replace(".TWO", ""): {
            "lots": p["shares"] // 1000,
            "shares": p["shares"],
            "entry_price": p["entry_price"],
        }
        for t, p in paper_pos.items()
    }

    all_codes = set(broker_pos) | set(paper_mapped)
    for code in sorted(all_codes):
        b = broker_pos.get(code)
        p = paper_mapped.get(code)

        if b and not p:
            diffs.append(f"{code}: 券商有 {b['lots']} 張,帳本無")
        elif p and not b:
            diffs.append(f"{code}: 帳本有 {p['shares']} 股,券商無")
        elif b and p and b["lots"] != p["lots"]:
            diffs.append(
                f"{code}: 券商 {b['lots']} 張 vs 帳本 {p['shares']} 股"
                f"({p['lots']} 張)"
            )

    return diffs
