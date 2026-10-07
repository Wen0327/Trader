"""券商調倉執行器:盤中下單、成交追蹤、未成交重掛。

設計:
- value_screener.py 調倉後寫入 pending 清單(storage/broker_pending.json)
- 本腳本在盤中執行:讀 pending → 下單 → 確認成交 → 更新 pending
- 全部成交後清除 pending;未成交的下次執行時重掛
- 可由 launchd 每 30 分鐘跑一次,或手動觸發

用法:
  .venv/bin/python -m execution.broker_executor          # 自動判斷盤中
  .venv/bin/python -m execution.broker_executor --force   # 強制執行(不檢查盤中)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
PENDING_PATH = ROOT / "storage" / "broker_pending.json"

TW_TZ = timezone(timedelta(hours=8))
MARKET_OPEN_HOUR = 9
MARKET_CLOSE_HOUR = 13
MARKET_CLOSE_MINUTE = 30


def is_market_open(now: datetime | None = None) -> bool:
    """台股盤中:週一~五 9:00~13:30 TST。"""
    if now is None:
        now = datetime.now(TW_TZ)
    else:
        now = now.astimezone(TW_TZ)
    if now.weekday() >= 5:  # 六日
        return False
    t = now.hour * 60 + now.minute
    return MARKET_OPEN_HOUR * 60 <= t < MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MINUTE


def pending_from_paper_trades(trades: list[dict]) -> list[dict]:
    """把紙上帳本的交易轉成 pending 清單(跳過 split)。"""
    return [
        {
            "ticker": t["ticker"],
            "name": t.get("name", t["ticker"]),
            "side": t["side"],
            "shares": t["shares"],
            "price": t["price"],
            "filled": False,
        }
        for t in trades
        if t["side"] in ("buy", "sell")
    ]


def save_pending(pending: list[dict], path: Path = PENDING_PATH) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(pending, ensure_ascii=False, indent=1))


def load_pending(path: Path = PENDING_PATH) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def check_fills(pending: list[dict], broker: Any) -> list[dict]:
    """檢查每筆 pending 是否已成交。

    買入成交 = ticker 出現在券商持倉
    賣出成交 = ticker 不在券商持倉(已清空)
    """
    positions = broker.positions()
    for item in pending:
        if item["filled"]:
            continue
        code = item["ticker"].replace(".TWO", "").replace(".TW", "")
        has_position = code in positions
        if item["side"] == "buy" and has_position:
            item["filled"] = True
        elif item["side"] == "sell" and not has_position:
            item["filled"] = True
    return pending


def execute_pending(pending: list[dict], broker: Any) -> list[dict]:
    """對未成交的 pending 下單。回傳更新後的 pending。"""
    from execution.rebalancer import execute_trades, split_lots

    unfilled = [p for p in pending if not p["filled"]]
    if not unfilled:
        return pending

    results = execute_trades(unfilled, broker)
    # 標記成功送單的(不代表成交,只是委託送出)
    for item, result in zip(unfilled, results):
        if result["status"] in ("ok", "partial"):
            item["submitted"] = True
    return pending


def run(force: bool = False) -> None:
    """主流程:讀 pending → 盤中檢查 → 下單/確認 → 更新。"""
    import os

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    from execution.shioaji_broker import ShioajiBroker
    from monitoring.notify import send

    if not force and not is_market_open():
        logger.info("非盤中,跳過")
        return

    pending = load_pending()
    if not pending:
        logger.info("無 pending 調倉")
        return

    unfilled = [p for p in pending if not p["filled"]]
    if not unfilled:
        logger.info("全部已成交,清除 pending")
        PENDING_PATH.unlink(missing_ok=True)
        return

    api_key = os.environ.get("SJ_API_KEY")
    secret_key = os.environ.get("SJ_SECRET_KEY")
    if not api_key or not secret_key:
        logger.error("SJ_API_KEY / SJ_SECRET_KEY 未設定")
        return

    broker = ShioajiBroker(
        api_key=api_key,
        secret_key=secret_key,
        simulation=os.environ.get("SJ_SIMULATION", "1") == "1",
        ca_path=os.environ.get("SJ_CA_PATH"),
        ca_passwd=os.environ.get("SJ_CA_PASSWD"),
        person_id=os.environ.get("SJ_PERSON_ID"),
    )

    try:
        # 1. 先確認之前的單有沒有成交
        pending = check_fills(pending, broker)

        # 2. 未成交的重新下單
        still_unfilled = [p for p in pending if not p["filled"]]
        if still_unfilled:
            from execution.rebalancer import execute_trades, format_discord_report
            from execution.shioaji_broker import reconcile

            results = execute_trades(still_unfilled, broker)
            n_ok = sum(1 for r in results if r["status"] == "ok")
            n_err = sum(1 for r in results if r["status"] == "error")
            logger.info("下單 %d 筆,成功 %d,失敗 %d", len(results), n_ok, n_err)

            if n_err > 0:
                send(f"⚠️ 調倉下單:{n_ok} 成功 / {n_err} 失敗,待重試")

        # 3. 再次確認成交
        pending = check_fills(pending, broker)
        save_pending(pending)

        all_filled = all(p["filled"] for p in pending)
        if all_filled:
            # 全部成交 → 對帳 + 清除
            from execution.shioaji_broker import reconcile
            from data.tw_paper import STATE_PATH

            broker_pos = broker.positions()
            paper_pos = json.loads(STATE_PATH.read_text())["positions"]
            diffs = reconcile(broker_pos, paper_pos)

            if diffs:
                send("⚠️ 調倉完成但對帳有差異:\n" + "\n".join(diffs))
            else:
                send("✅ 調倉全部成交,對帳一致")

            PENDING_PATH.unlink(missing_ok=True)
            logger.info("全部成交,pending 已清除")
        else:
            n_left = sum(1 for p in pending if not p["filled"])
            logger.info("尚有 %d 筆未成交,下次盤中繼續", n_left)

    finally:
        broker.logout()


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="強制執行(不檢查盤中)")
    args = parser.parse_args()
    run(force=args.force)
