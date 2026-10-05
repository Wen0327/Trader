"""調倉執行器:讀紙上帳本的交易,轉成券商下單指令。

純函式模組,不維護狀態,不管理 broker 連線。
呼叫者負責 broker 登入/登出和錯誤處理。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class LotSplit(TypedDict):
    lots: int
    odd_shares: int


class OrderResult(TypedDict):
    ticker: str
    name: str
    side: str
    shares: int
    lots: int
    odd_shares: int
    status: str  # "ok" | "partial" | "skipped" | "error"
    error: str | None


def split_lots(shares: int) -> LotSplit:
    """股數拆成整張 + 零股。1 張 = 1000 股。"""
    return {"lots": shares // 1000, "odd_shares": shares % 1000}


def extract_today_trades(
    state_path: Path,
    today: str | None = None,
) -> list[dict]:
    """從 state JSON 讀取今天的 buy/sell 交易(跳過 split)。"""
    if not state_path.exists():
        return []
    state = json.loads(state_path.read_text())
    if today is None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        t for t in state.get("trades", [])
        if t["date"] == today and t["side"] in ("buy", "sell")
    ]


def execute_trades(trades: list[dict], broker: Any) -> list[OrderResult]:
    """對每筆交易拆整張/零股下單。每筆獨立 try/except,一筆失敗不擋其他。"""
    from execution.shioaji_broker import BrokerError

    results: list[OrderResult] = []
    for t in trades:
        ticker = t["ticker"]
        name = t.get("name", ticker)
        side = t["side"]
        shares = t["shares"]
        price = t["price"]

        if side not in ("buy", "sell"):
            results.append(_result(t, 0, 0, "skipped", None))
            continue

        split = split_lots(shares)
        if split["lots"] == 0 and split["odd_shares"] == 0:
            results.append(_result(t, 0, 0, "skipped", None))
            continue

        action = broker.buy if side == "buy" else broker.sell
        action_odd = broker.buy_odd if side == "buy" else broker.sell_odd
        lot_ok = False
        odd_ok = False
        error = None

        try:
            if split["lots"] > 0:
                action(ticker, price, split["lots"])
                lot_ok = True
            if split["odd_shares"] > 0:
                action_odd(ticker, price, split["odd_shares"])
                odd_ok = True
        except BrokerError as e:
            error = str(e)

        needed_lot = split["lots"] > 0
        needed_odd = split["odd_shares"] > 0
        all_ok = (not needed_lot or lot_ok) and (not needed_odd or odd_ok)

        if all_ok:
            status = "ok"
        elif lot_ok or odd_ok:
            status = "partial"
        else:
            status = "error"

        results.append(_result(t, split["lots"], split["odd_shares"], status, error))

    return results


def _result(t: dict, lots: int, odd: int, status: str, error: str | None) -> OrderResult:
    return {
        "ticker": t["ticker"],
        "name": t.get("name", t["ticker"]),
        "side": t["side"],
        "shares": t["shares"],
        "lots": lots,
        "odd_shares": odd,
        "status": status,
        "error": error,
    }


SIDE_LABEL = {"buy": "買入", "sell": "賣出"}


def format_discord_report(results: list[OrderResult], reconciliation: list[str]) -> str:
    """格式化執行結果 + 對帳差異為 Discord 訊息。"""
    lines = ["## 🔄 券商調倉執行"]

    if not results:
        lines.append("無交易需執行")
    else:
        for r in results:
            side = SIDE_LABEL.get(r["side"], r["side"])
            status = {"ok": "✅", "partial": "⚠️", "skipped": "⏭️", "error": "❌"}[r["status"]]
            detail = f"{r['lots']}張"
            if r["odd_shares"]:
                detail += f"+{r['odd_shares']}股"
            line = f"{status} {side} {r['ticker']} {r['name']} {detail}"
            if r["error"]:
                line += f" — {r['error']}"
            lines.append(line)

    if reconciliation:
        lines.append("\n⚠️ 對帳差異:")
        lines.extend(f"  {d}" for d in reconciliation)
    else:
        lines.append("\n✅ 對帳:券商 ≡ 帳本")

    return "\n".join(lines)
