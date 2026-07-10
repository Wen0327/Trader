"""台股紙上帳本:跟隨動量 TOP10(cap150)季調倉的虛擬持倉。

台幣計價,台股實際費制(買 0.1425%、賣 0.1425%+證交稅 0.3%)。
誠實條款:成交按最新收盤/報價,無盤口深度 — 紙上績效為實盤上界;
所有損益如實入帳,用於對帳回測期望,不是成績單。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "storage" / "tw_paper_state.json"
INITIAL_CASH = 1_000_000.0
BUY_FEE = 0.001425
SELL_FEE = 0.001425 + 0.003  # 手續費 + 證交稅


def _load() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"cash": INITIAL_CASH, "positions": {}, "started": None, "trades": []}


def _save(state: dict) -> None:
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))


def process(picks: list[dict], prices: dict[str, float],
            rebalance_due: bool) -> dict:
    """換倉(若季度到期或首次)+ 按市價估值。回傳帳本摘要。"""
    state = _load()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    first_run = state["started"] is None

    if rebalance_due or first_run:
        # 全數平倉
        for t, pos in list(state["positions"].items()):
            px = prices.get(t)
            if px is None:
                continue  # 無報價,留倉待下次
            proceeds = pos["shares"] * px * (1 - SELL_FEE)
            state["cash"] += proceeds
            state["trades"].append({
                "date": now, "side": "sell", "ticker": t,
                "name": pos.get("name", t),
                "shares": pos["shares"], "price": px,
                "pnl_pct": round((px / pos["entry_price"] - 1) * 100, 2),
            })
            del state["positions"][t]

        # 等權買入新名單
        buyable = [p for p in picks if prices.get(p["ticker"])]
        if buyable:
            alloc = state["cash"] / len(buyable)
            for p in buyable:
                px = prices[p["ticker"]]
                shares = int(alloc / (px * (1 + BUY_FEE)))  # 整股
                if shares <= 0:
                    continue
                cost = shares * px * (1 + BUY_FEE)
                state["cash"] -= cost
                state["positions"][p["ticker"]] = {
                    "shares": shares, "entry_price": px, "entry_date": now,
                    "name": p["name"],
                }
                state["trades"].append({
                    "date": now, "side": "buy", "ticker": p["ticker"],
                    "name": p["name"],
                    "shares": shares, "price": px, "pnl_pct": None,
                })
        if first_run:
            state["started"] = now

    # 市價估值
    holdings = []
    market_value = 0.0
    for t, pos in state["positions"].items():
        px = prices.get(t, pos["entry_price"])
        value = pos["shares"] * px
        market_value += value
        holdings.append({
            "ticker": t, "name": pos.get("name", t),
            "shares": pos["shares"], "entry_price": pos["entry_price"],
            "price": px,
            "pnl_pct": round((px / pos["entry_price"] - 1) * 100, 2),
        })
    equity = round(state["cash"] + market_value, 0)
    _save(state)

    return {
        "equity": equity,
        "cash": round(state["cash"], 0),
        "started": state["started"],
        "return_pct": round((equity / INITIAL_CASH - 1) * 100, 2),
        "holdings": sorted(holdings, key=lambda h: -h["pnl_pct"]),
        "n_trades": len(state["trades"]),
    }
