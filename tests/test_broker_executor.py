"""券商調倉執行器:盤中執行、成交追蹤、未成交重掛。"""

import json
from unittest.mock import MagicMock, patch

import pytest

from execution.broker_executor import (
    MARKET_CLOSE_HOUR,
    MARKET_OPEN_HOUR,
    check_fills,
    is_market_open,
    is_trading_day,
    load_pending,
    needs_submit,
    pending_from_paper_trades,
    save_pending,
)


def _trade(side="buy", ticker="2330.TW", shares=467, price=580.0):
    return {"date": "2026-10-05", "side": side, "ticker": ticker,
            "name": "台積電", "shares": shares, "price": price, "pnl_pct": None}


# ── 盤中判斷 ─────────────────────────────────────────────

class TestIsMarketOpen:
    def test_during_trading_hours(self):
        from datetime import datetime, timezone, timedelta
        tw = timezone(timedelta(hours=8))
        # 10:00 TST = 盤中
        dt = datetime(2026, 10, 7, 10, 0, tzinfo=tw)
        assert is_market_open(dt) is True

    def test_before_open(self):
        from datetime import datetime, timezone, timedelta
        tw = timezone(timedelta(hours=8))
        dt = datetime(2026, 10, 7, 8, 30, tzinfo=tw)
        assert is_market_open(dt) is False

    def test_after_close(self):
        from datetime import datetime, timezone, timedelta
        tw = timezone(timedelta(hours=8))
        dt = datetime(2026, 10, 7, 14, 0, tzinfo=tw)
        assert is_market_open(dt) is False

    def test_weekend(self):
        from datetime import datetime, timezone, timedelta
        tw = timezone(timedelta(hours=8))
        # 2026-10-10 is Saturday
        dt = datetime(2026, 10, 10, 10, 0, tzinfo=tw)
        assert is_market_open(dt) is False


# ── Pending 狀態管理 ─────────────────────────────────────

class TestPendingState:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "pending.json"
        pending = [
            {"ticker": "2330.TW", "side": "buy", "shares": 467, "price": 580.0,
             "filled": False},
        ]
        save_pending(pending, path)
        loaded = load_pending(path)
        assert len(loaded) == 1
        assert loaded[0]["ticker"] == "2330.TW"

    def test_load_missing_returns_empty(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        assert load_pending(path) == []


# ── 從紙上交易生成 pending ───────────────────────────────

class TestPendingFromPaperTrades:
    def test_creates_pending_items(self):
        trades = [_trade(), _trade(side="sell", ticker="2317.TW", shares=1000)]
        pending = pending_from_paper_trades(trades)
        assert len(pending) == 2
        assert pending[0]["filled"] is False
        assert pending[1]["side"] == "sell"

    def test_skips_split(self):
        trades = [{"date": "2026-10-05", "side": "split", "ticker": "X",
                   "shares": 19, "price": None, "pnl_pct": None}]
        pending = pending_from_paper_trades(trades)
        assert pending == []


# ── 成交確認 ─────────────────────────────────────────────

class TestCheckFills:
    def test_marks_filled(self):
        broker = MagicMock()
        broker.positions.return_value = {"2330": {"lots": 0, "avg_price": 580.0}}
        pending = [
            {"ticker": "2330.TW", "side": "buy", "shares": 467,
             "price": 580.0, "filled": False},
        ]
        updated = check_fills(pending, broker)
        assert updated[0]["filled"] is True

    def test_unfilled_stays_pending(self):
        broker = MagicMock()
        broker.positions.return_value = {}
        pending = [
            {"ticker": "2330.TW", "side": "buy", "shares": 467,
             "price": 580.0, "filled": False},
        ]
        updated = check_fills(pending, broker)
        assert updated[0]["filled"] is False

    def test_already_filled_unchanged(self):
        broker = MagicMock()
        broker.positions.return_value = {}
        pending = [
            {"ticker": "2330.TW", "side": "buy", "shares": 467,
             "price": 580.0, "filled": True},
        ]
        updated = check_fills(pending, broker)
        assert updated[0]["filled"] is True

    def test_sell_filled_when_not_in_positions(self):
        """賣出成交 = 該股不在券商持倉裡了。"""
        broker = MagicMock()
        broker.positions.return_value = {}  # 沒有 2317 了
        pending = [
            {"ticker": "2317.TW", "side": "sell", "shares": 1000,
             "price": 200.0, "filled": False},
        ]
        updated = check_fills(pending, broker)
        assert updated[0]["filled"] is True


# ── 重複下單防護 ─────────────────────────────────────────

class TestNeedsSubmit:
    def test_unfilled_no_open_order(self):
        item = {"ticker": "2330.TW", "side": "buy", "shares": 467,
                "price": 580.0, "filled": False, "last_submitted": None}
        assert needs_submit(item, "2026-10-07", set()) is True

    def test_already_filled(self):
        item = {"ticker": "2330.TW", "side": "buy", "shares": 467,
                "price": 580.0, "filled": True, "last_submitted": None}
        assert needs_submit(item, "2026-10-07", set()) is False

    def test_has_open_order_in_broker(self):
        """券商已有該股掛單 → 不重掛。"""
        item = {"ticker": "2330.TW", "side": "buy", "shares": 467,
                "price": 580.0, "filled": False, "last_submitted": None}
        assert needs_submit(item, "2026-10-07", {"2330"}) is False

    def test_submitted_today_already(self):
        """今天已經掛過 → 不重掛。"""
        item = {"ticker": "2330.TW", "side": "buy", "shares": 467,
                "price": 580.0, "filled": False, "last_submitted": "2026-10-07"}
        assert needs_submit(item, "2026-10-07", set()) is False

    def test_submitted_yesterday_resubmits(self):
        """昨天掛的今天過期了 → 重掛。"""
        item = {"ticker": "2330.TW", "side": "buy", "shares": 467,
                "price": 580.0, "filled": False, "last_submitted": "2026-10-06"}
        assert needs_submit(item, "2026-10-07", set()) is True

    def test_two_suffix_matches_open_order(self):
        """上櫃股 .TWO 後綴要正確對應券商的純數字代號。"""
        item = {"ticker": "3529.TWO", "side": "buy", "shares": 100,
                "price": 800.0, "filled": False, "last_submitted": None}
        assert needs_submit(item, "2026-10-07", {"3529"}) is False


# ── 假日偵測 ─────────────────────────────────────────────

class TestIsTradingDay:
    def test_has_volume_is_trading_day(self):
        broker = MagicMock()
        snap = MagicMock()
        snap.total_volume = 5000
        broker.api.contracts.get.return_value = MagicMock()
        broker.api.snapshots.return_value = [snap]
        assert is_trading_day(broker) is True

    def test_zero_volume_is_holiday(self):
        broker = MagicMock()
        snap = MagicMock()
        snap.total_volume = 0
        broker.api.contracts.get.return_value = MagicMock()
        broker.api.snapshots.return_value = [snap]
        assert is_trading_day(broker) is False

    def test_error_defaults_to_open(self):
        broker = MagicMock()
        broker.api.contracts.get.side_effect = Exception("fail")
        assert is_trading_day(broker) is True
