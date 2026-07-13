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
    if os.environ.get("DISCORD_MUTED", "").strip() == "1":
        return  # 研究期靜音(.env DISCORD_MUTED=1;移除即恢復)
    webhook = os.environ.get("DISCORD_WEBHOOK", "").strip()
    if not webhook:
        return
    try:
        requests.post(webhook, json={"content": message[:1900]}, timeout=10)
    except Exception as e:
        log.warning(f"Discord 通知發送失敗(不影響主流程): {e}")


def alert_on_crash(job_name: str) -> None:
    """排程腳本防沉默失敗:未捕捉例外先發 Discord 警報,再走預設 hook。

    背景:2026-07-13 台股週掃因 Yahoo 斷線 crash,無人知曉、
    差點爛一週(週更任務下次自動重跑是下週)。
    在腳本 import 後呼叫一次即生效。
    """
    import sys

    def hook(exc_type, exc, tb):
        send(f"🚨 {job_name} 失敗:{exc_type.__name__}: {exc}")
        sys.__excepthook__(exc_type, exc, tb)  # traceback 照印、exit code 不變

    sys.excepthook = hook
