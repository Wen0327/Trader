"""輪動狀態變遷偵測:比對前次掃描,產生值得通知的事件。

事件類型(全部是客觀事件,層次1+2 設計,2026-07-09):
- 狀態升級/降級(含 🟢 訊號誕生與死亡)
- 輪動比值翻轉(啟動/熄火)
附 K 棒解剖描述(實體佔比、收盤位置、量能倍數)。
首次執行只存基準,不發通知。
"""

from __future__ import annotations

import json
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "storage" / "rotation_status.json"


def _bar_desc(item: dict) -> str:
    bar = item.get("bar")
    if not bar:
        return ""
    color = "陽" if bar["up"] else "陰"
    return (f"|{color}線實體 {bar['body_pct']}%・收在區間 {bar['close_pos']}%"
            f"・量 {bar['vol_mult']}x")


def detect(rotation: dict) -> list[str]:
    """回傳事件訊息列表,並更新基準狀態。"""
    prev = {}
    if STATE_PATH.exists():
        prev = json.loads(STATE_PATH.read_text())
    first_run = not prev

    events: list[str] = []
    curr: dict = {"tickers": {}, "ratios": {}}

    for w in rotation.get("watchlist", []):
        t = w["ticker"]
        rank = w.get("status_rank", 0)
        curr["tickers"][t] = rank
        if first_run:
            continue
        old = prev.get("tickers", {}).get(t)
        if old is None or old == rank:
            continue
        label = w.get("status_label", "")
        if rank == 4 and old < 4:
            events.append(f"🟢 **{t}** 訊號誕生 → {label}{_bar_desc(w)}")
        elif rank < 4 and old == 4:
            events.append(f"📉 **{t}** 訊號死亡(跌破20日低)→ {label}{_bar_desc(w)}")
        elif rank > old:
            events.append(f"⬆️ **{t}** 升級 → {label}{_bar_desc(w)}")
        else:
            events.append(f"⬇️ **{t}** 降級 → {label}")

    for r in rotation.get("ratios", []):
        pair = r["pair"]
        on = bool(r["rotation_on"])
        curr["ratios"][pair] = on
        if first_run:
            continue
        old = prev.get("ratios", {}).get(pair)
        if old is None or old == on:
            continue
        events.append(
            f"{'🟢' if on else '⚪'} 輪動比值 **{pair}** "
            f"{'站上' if on else '跌回'} 200MA({r['pct_vs_ma200']:+.1f}%)")

    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(curr, ensure_ascii=False))
    return events
