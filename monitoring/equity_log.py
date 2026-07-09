"""權益快照:每次 bot 循環把各軌道權益寫進 JSONL。

取代「從 bot.log 解析權益」的脆弱做法 — 日誌會輪替,快照不會丟。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "storage" / "equity_history.jsonl"


def record(track: str, equity: float) -> None:
    PATH.parent.mkdir(exist_ok=True)
    with PATH.open("a") as f:
        f.write(json.dumps({
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "track": track,
            "equity": round(equity, 2),
        }) + "\n")


def read(track: str = "spot") -> list[dict]:
    if not PATH.exists():
        return []
    out = []
    for line in PATH.read_text().splitlines():
        try:
            row = json.loads(line)
            if row.get("track") == track:
                out.append({"ts": row["ts"], "equity": row["equity"]})
        except json.JSONDecodeError:
            continue
    return out
