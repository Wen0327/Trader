"""Rebalancer:lot split、trade 執行、Discord 報告。全 mock。"""

import json
from unittest.mock import MagicMock

import pytest

from execution.rebalancer import (
    execute_trades,
    extract_today_trades,
    format_discord_report,
    split_lots,
)
from execution.shioaji_broker import BrokerError


def _trade(side="buy", ticker="2330.TW", shares=1500, price=580.0, date="2026-10-05"):
    return {"date": date, "side": side, "ticker": ticker,
            "name": "台積電", "shares": shares, "price": price, "pnl_pct": None}


def _broker():
    b = MagicMock()
    b.buy.return_value = MagicMock()
    b.sell.return_value = MagicMock()
    b.buy_odd.return_value = MagicMock()
    b.sell_odd.return_value = MagicMock()
    return b


# ── split_lots ───────────────────────────────────────────

class TestSplitLots:
    def test_exact_lots(self):
        assert split_lots(3000) == {"lots": 3, "odd_shares": 0}

    def test_with_remainder(self):
        assert split_lots(1500) == {"lots": 1, "odd_shares": 500}

    def test_odd_only(self):
        assert split_lots(467) == {"lots": 0, "odd_shares": 467}

    def test_zero(self):
        assert split_lots(0) == {"lots": 0, "odd_shares": 0}


# ── extract_today_trades ─────────────────────────────────

class TestExtractTodayTrades:
    def _write_state(self, tmp_path, trades):
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"trades": trades}))
        return path

    def test_filters_by_date(self, tmp_path):
        path = self._write_state(tmp_path, [
            _trade(date="2026-10-04"),
            _trade(date="2026-10-05"),
            _trade(date="2026-10-05", side="sell"),
        ])
        result = extract_today_trades(path, today="2026-10-05")
        assert len(result) == 2

    def test_skips_split_trades(self, tmp_path):
        path = self._write_state(tmp_path, [
            _trade(date="2026-10-05"),
            {"date": "2026-10-05", "side": "split", "ticker": "6669.TW",
             "name": "緯穎", "shares": 19, "price": None, "pnl_pct": None},
        ])
        result = extract_today_trades(path, today="2026-10-05")
        assert len(result) == 1
        assert result[0]["side"] == "buy"

    def test_empty_when_no_match(self, tmp_path):
        path = self._write_state(tmp_path, [_trade(date="2026-10-04")])
        assert extract_today_trades(path, today="2026-10-05") == []

    def test_missing_file_returns_empty(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        assert extract_today_trades(path, today="2026-10-05") == []


# ── execute_trades ───────────────────────────────────────

class TestExecuteTrades:
    def test_buy_lots_and_odd(self):
        broker = _broker()
        results = execute_trades([_trade(shares=1500)], broker)
        broker.buy.assert_called_once_with("2330.TW", 580.0, 1)
        broker.buy_odd.assert_called_once_with("2330.TW", 580.0, 500)
        assert results[0]["status"] == "ok"

    def test_sell_odd_only(self):
        broker = _broker()
        results = execute_trades([_trade(side="sell", shares=467)], broker)
        broker.sell.assert_not_called()
        broker.sell_odd.assert_called_once_with("2330.TW", 580.0, 467)
        assert results[0]["status"] == "ok"

    def test_buy_exact_lots_no_odd(self):
        broker = _broker()
        results = execute_trades([_trade(shares=2000)], broker)
        broker.buy.assert_called_once_with("2330.TW", 580.0, 2)
        broker.buy_odd.assert_not_called()

    def test_zero_shares_skipped(self):
        broker = _broker()
        results = execute_trades([_trade(shares=0)], broker)
        broker.buy.assert_not_called()
        broker.buy_odd.assert_not_called()
        assert results[0]["status"] == "skipped"

    def test_split_side_skipped(self):
        broker = _broker()
        t = _trade()
        t["side"] = "split"
        results = execute_trades([t], broker)
        broker.buy.assert_not_called()
        broker.sell.assert_not_called()
        assert results[0]["status"] == "skipped"

    def test_error_does_not_abort_other_trades(self):
        broker = _broker()
        broker.buy.side_effect = [BrokerError("fail"), MagicMock()]
        trades = [_trade(ticker="BAD.TW", shares=1000),
                  _trade(ticker="2330.TW", shares=1000)]
        results = execute_trades(trades, broker)
        assert results[0]["status"] == "error"
        assert results[1]["status"] == "ok"

    def test_partial_when_lot_ok_odd_fails(self):
        broker = _broker()
        broker.buy_odd.side_effect = BrokerError("odd fail")
        results = execute_trades([_trade(shares=1500)], broker)
        assert results[0]["status"] == "partial"
        assert results[0]["error"] == "odd fail"


# ── format_discord_report ────────────────────────────────

class TestFormatDiscordReport:
    def test_includes_trade_info(self):
        results = [{
            "ticker": "2330.TW", "name": "台積電", "side": "buy",
            "shares": 1500, "lots": 1, "odd_shares": 500,
            "status": "ok", "error": None,
        }]
        report = format_discord_report(results, [])
        assert "2330" in report
        assert "買入" in report

    def test_includes_diffs(self):
        report = format_discord_report([], ["2330: 券商有 1 張,帳本無"])
        assert "2330" in report

    def test_empty_is_valid(self):
        report = format_discord_report([], [])
        assert isinstance(report, str)
