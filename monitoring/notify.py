"""通知推播:Discord webhook。

.env 設定 DISCORD_WEBHOOK 即啟用;未設定時所有呼叫靜默跳過(no-op),
系統其他部分不需要知道通知是否開啟。發送失敗絕不拋例外 —
通知是輔助功能,不允許它弄死交易主流程。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

log = logging.getLogger("notify")


def send(message: str) -> None:
    webhook = os.environ.get("DISCORD_WEBHOOK", "").strip()
    if not webhook:
        return
    try:
        requests.post(webhook, json={"content": message[:1900]}, timeout=10)
    except Exception as e:
        log.warning(f"Discord 通知發送失敗(不影響主流程): {e}")
