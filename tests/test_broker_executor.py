"""券商調倉執行器:盤中執行、成交追蹤、未成交重掛。"""

import json
from unittest.mock import MagicMock, patch

import pytest

from execution.broker_executor import (
    MARKET_CLOSE_HOUR,
    MARKET_OPEN_HOUR,
    check_fills,
    is_market_open,
    load_pending,
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
