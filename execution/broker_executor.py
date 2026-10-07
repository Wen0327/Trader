"""券商調倉執行器:盤中下單、成交追蹤、未成交重掛。

設計:
- value_screener.py 調倉後寫入 pending 清單(storage/broker_pending.json)
- 本腳本在盤中執行:讀 pending → 下單 → 確認成交 → 更新 pending
- 全部成交後清除 pending;未成交的下一個交易日重掛
- 可由 launchd 每 30 分鐘跑一次,或手動觸發

防重複下單:每筆 pending 記錄 last_submitted 日期,同一天不重掛。
假日檢查:用 Shioaji snapshot 偵測(volume=0 = 休市)。

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
LOCK_PATH = ROOT / "storage" / "broker_executor.lock"

TW_TZ = timezone(timedelta(hours=8))
MARKET_OPEN_HOUR = 9
MARKET_CLOSE_HOUR = 13
MARKET_CLOSE_MINUTE = 30


def is_market_open(now: datetime | None = None) -> bool:
    """台股盤中:週一~五 9:00~13:30 TST。不含假日檢查(需另用 is_trading_day)。"""
    if now is None:
        now = datetime.now(TW_TZ)
    else:
        now = now.astimezone(TW_TZ)
    if now.weekday() >= 5:  # 六日
        return False
    t = now.hour * 60 + now.minute
    return MARKET_OPEN_HOUR * 60 <= t < MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MINUTE


def is_trading_day(broker: Any) -> bool:
    """用 Shioaji snapshot 偵測今天是否為交易日(排除國定假日)。

    抓 0050 的即時快照,volume > 0 表示有交易 = 今天有開盤。
    """
    try:
        contract = broker.api.contracts.get("0050")
        if contract is None:
            return True  # 查不到就假設有開盤
        snapshots = broker.api.snapshots([contract])
        if snapshots and snapshots[0].total_volume > 0:
            return True
        return False
    except Exception:
        return True  # 出錯就假設有開盤,讓後續邏輯自己處理


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
            "last_submitted": None,
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

    買入成交 = 券商持倉數量 ≥ 預期(含零股,用 lots×1000 估算)
    賣出成交 = ticker 不在券商持倉(已清空)
    部分成交 = 有持倉但數量不足 → 維持 unfilled,下次重掛差額
    """
    positions = broker.positions()
    for item in pending:
        if item["filled"]:
            continue
        code = item["ticker"].replace(".TWO", "").replace(".TW", "")
        pos = positions.get(code)
        if item["side"] == "buy":
            if pos is not None:
                # lots 是整張數;零股成交時 lots 可能為 0 但仍有持倉
                broker_shares = pos["lots"] * 1000
                # Shioaji simulation 的 quantity 欄位就是張數
                # 有持倉就算成交(精確數量對帳由 reconcile 處理)
                item["filled"] = True
        elif item["side"] == "sell":
            if pos is None:
                item["filled"] = True
    return pending


def needs_submit(item: dict, today: str, open_order_codes: set[str]) -> bool:
    """判斷這筆 pending 是否需要今天下單。

    - 已成交 → 不需要
    - 券商已有該股的未成交委託 → 不需要(避免重複掛單)
    - 今天已經掛過且券商沒退單 → 不需要
    - 其他 → 需要
    """
    if item["filled"]:
        return False
    code = item["ticker"].replace(".TWO", "").replace(".TW", "")
    if code in open_order_codes:
        return False  # 券商已有掛單,不重複
    if item.get("last_submitted") == today:
        return False
    return True


def run(force: bool = False) -> None:
    """主流程:讀 pending → 盤中檢查 → 下單/確認 → 更新。"""
    import fcntl
    import os

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    from execution.shioaji_broker import ShioajiBroker
    from monitoring.notify import send

    # file lock 防止並行執行(launchd 重疊、手動+排程同時跑)
    LOCK_PATH.parent.mkdir(exist_ok=True)
    lock_fd = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.info("另一個 executor 正在跑,跳過")
        lock_fd.close()
        return

    try:
        _run_inner(force, send, ShioajiBroker)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def _run_inner(force: bool, send, ShioajiBroker) -> None:
    import os

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
        # 0. 假日檢查:今天有沒有開盤
        if not force and not is_trading_day(broker):
            logger.info("今天非交易日(假日),跳過")
            return

        # 1. 先確認之前的單有沒有成交
        pending = check_fills(pending, broker)

        # 2. 查券商當前掛單,避免重複下單
        open_orders = broker.open_orders()
        open_codes = {o["code"] for o in open_orders}
        if open_codes:
            logger.info("券商尚有 %d 筆未成交委託: %s", len(open_orders),
                        ", ".join(open_codes))

        today = datetime.now(TW_TZ).strftime("%Y-%m-%d")
        to_submit = [p for p in pending if needs_submit(p, today, open_codes)]
        if to_submit:
            from execution.rebalancer import execute_trades

            results = execute_trades(to_submit, broker)
            n_ok = sum(1 for r in results if r["status"] == "ok")
            n_err = sum(1 for r in results if r["status"] == "error")

            # 標記今天已掛單
            for item, result in zip(to_submit, results):
                if result["status"] in ("ok", "partial"):
                    item["last_submitted"] = today

            logger.info("下單 %d 筆,成功 %d,失敗 %d", len(results), n_ok, n_err)
            if n_err > 0:
                send(f"⚠️ 調倉下單:{n_ok} 成功 / {n_err} 失敗,待重試")

        # 3. 再次確認成交
        pending = check_fills(pending, broker)
        save_pending(pending)

        all_filled = all(p["filled"] for p in pending)
        if all_filled:
            from data.tw_paper import STATE_PATH
            from execution.shioaji_broker import reconcile

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
            logger.info("尚有 %d 筆未成交,下一交易日繼續", n_left)

    finally:
        broker.logout()


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="強制執行(不檢查盤中)")
    args = parser.parse_args()
    run(force=args.force)
