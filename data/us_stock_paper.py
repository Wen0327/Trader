"""美股個股紙上帳本:只交易「edge 閘門通過 + Donchian 訊號存續」的個股。

進出場由每日掃描的狀態機驅動:訊號誕生買入、訊號死亡賣出 —
不追開帳前已存在的訊號(等新觸發 = 合適的時候才交易)。
費用:零佣金時代,計 0.1% 滑價緩衝。碎股允許(美股常態)。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "storage" / "us_stock_paper_state.json"
INITIAL_CASH = 10_000.0
SLIPPAGE = 0.001
POSITION_PCT = 0.25   # 每檔 25% 權益
MAX_POSITIONS = 4


def _load() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"cash": INITIAL_CASH, "positions": {}, "started": None,
            "trades": [], "seen_active": []}


def process(watchlist: list[dict]) -> dict:
    """輸入:輪動觀察清單(含 edge_passed / status_rank / price)。

    首次執行:記錄當下已存續的訊號為基準(不進場)— 只交易新觸發。
    回傳帳本摘要 + 本次事件。
    """
    state = _load()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    events: list[str] = []

    eligible = {w["ticker"]: w for w in watchlist
                if w.get("edge_passed") and w.get("price")}
    active = {t for t, w in eligible.items() if w.get("status_rank") == 4}

    if state["started"] is None:
        state["started"] = now
        state["seen_active"] = sorted(active)  # 既有訊號列為基準,不追
    seen = set(state["seen_active"])

    # 賣出:持倉中訊號已死亡者
    for t, pos in list(state["positions"].items()):
        w = eligible.get(t)
        still_active = w is not None and w.get("status_rank") == 4
        if still_active:
            continue
        px = (w["price"] if w else pos["entry_price"]) * (1 - SLIPPAGE)
        state["cash"] += pos["shares"] * px
        pnl = round((px / pos["entry_price"] - 1) * 100, 2)
        state["trades"].append({
            "date": now, "side": "sell", "ticker": t,
            "name": pos.get("name", t), "shares": pos["shares"],
            "price": round(px, 2), "pnl_pct": pnl,
        })
        events.append(f"📗 個股帳:賣出 {t}(訊號死亡)損益 {pnl:+}%")
        del state["positions"][t]

    # 買入:新觸發(不在基準內、未持有、有額度)
    equity_now = state["cash"] + sum(
        p["shares"] * eligible.get(t, {}).get("price", p["entry_price"])
        for t, p in state["positions"].items())
    for t in sorted(active):
        if t in seen or t in state["positions"]:
            continue
        if len(state["positions"]) >= MAX_POSITIONS:
            events.append(f"📗 個股帳:{t} 觸發但倉位已滿,略過")
            continue
        px = eligible[t]["price"] * (1 + SLIPPAGE)
        budget = min(equity_now * POSITION_PCT, state["cash"])
        shares = round(budget / px, 4)
        if shares <= 0:
            continue
        state["cash"] -= shares * px
        state["positions"][t] = {
            "shares": shares, "entry_price": round(px, 2),
            "entry_date": now, "name": eligible[t].get("label", t),
        }
        state["trades"].append({
            "date": now, "side": "buy", "ticker": t,
            "name": eligible[t].get("label", t), "shares": shares,
            "price": round(px, 2), "pnl_pct": None,
        })
        events.append(f"📗 個股帳:買入 {t} @ {px:.2f}(訊號誕生)")

    state["seen_active"] = sorted(active)  # 更新基準

    # 估值
    holdings = []
    mv = 0.0
    for t, pos in state["positions"].items():
        px = eligible.get(t, {}).get("price", pos["entry_price"])
        mv += pos["shares"] * px
        holdings.append({
            "ticker": t, "name": pos.get("name", t),
            "shares": pos["shares"], "entry_price": pos["entry_price"],
            "price": px,
            "pnl_pct": round((px / pos["entry_price"] - 1) * 100, 2),
        })
    equity = round(state["cash"] + mv, 2)
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))

    return {
        "equity": equity,
        "cash": round(state["cash"], 2),
        "started": state["started"],
        "return_pct": round((equity / INITIAL_CASH - 1) * 100, 2),
        "holdings": holdings,
        "n_trades": len(state["trades"]),
        "eligible_now": sorted(eligible),
        "events": events,
    }
