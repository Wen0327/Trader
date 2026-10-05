"""/api/paper/trades 端點:已實現/未實現損益匯總計算。

直接呼叫 endpoint function 測試邏輯,避免 auth middleware 的複雜度。
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _build_state(trades: list[dict]) -> dict:
    return {"cash": 50_000, "positions": {}, "started": "2026-07-10",
            "trades": trades}


def _call(tmp_path: Path, state: dict, report_paper: dict | None = None,
          book: str = "tw"):
    """直接呼叫 paper_all_trades,注入 tmp state + report。"""
    state_name = "tw_paper_state.json" if book == "tw" else "tw_paper_d_state.json"
    storage = tmp_path / "storage"
    storage.mkdir(exist_ok=True)
    (storage / state_name).write_text(json.dumps(state))

    reports = tmp_path / "reports"
    reports.mkdir(exist_ok=True)
    report = {"paper": report_paper or {}, "paper_d": report_paper or {}}
    (reports / "value_screen_2026-10-05.json").write_text(json.dumps(report))

    import dashboard.api as api_mod
    with (patch.object(api_mod, "ROOT", tmp_path),
          patch.object(api_mod, "scan_store", api_mod.ScanStore(reports))):
        return api_mod.paper_all_trades(book)


class TestRealizedPnl:
    TRADES = [
        {"side": "buy", "ticker": "2330.TW", "shares": 100, "price": 1000,
         "pnl_pct": None, "date": "2026-07-10", "name": "台積電"},
        {"side": "buy", "ticker": "2317.TW", "shares": 200, "price": 250,
         "pnl_pct": None, "date": "2026-07-10", "name": "鴻海"},
        # 台積電: 1000→1200 = +20%
        {"side": "sell", "ticker": "2330.TW", "shares": 100, "price": 1200,
         "pnl_pct": 20.0, "date": "2026-10-05", "name": "台積電"},
        # 鴻海: 250→200 = -20%
        {"side": "sell", "ticker": "2317.TW", "shares": 200, "price": 200,
         "pnl_pct": -20.0, "date": "2026-10-05", "name": "鴻海"},
    ]

    def test_total_pnl(self, tmp_path):
        r = _call(tmp_path, _build_state(self.TRADES))
        # 台積電: 100*(1200-1000) = +20,000; 鴻海: 200*(200-250) = -10,000
        assert r["summary"]["total_realized_pnl"] == 10_000

    def test_win_rate(self, tmp_path):
        r = _call(tmp_path, _build_state(self.TRADES))
        assert r["summary"]["win_rate"] == 50.0

    def test_avg_win_and_loss(self, tmp_path):
        r = _call(tmp_path, _build_state(self.TRADES))
        assert r["summary"]["avg_win"] == 20_000
        assert r["summary"]["avg_loss"] == -10_000

    def test_n_sells(self, tmp_path):
        r = _call(tmp_path, _build_state(self.TRADES))
        assert r["summary"]["n_sells"] == 2


class TestUnrealizedPnl:
    def test_from_holdings(self, tmp_path):
        holdings = [
            {"ticker": "2454.TW", "name": "聯發科", "shares": 10,
             "entry_price": 800, "price": 900, "pnl_pct": 12.5},
        ]
        r = _call(tmp_path, _build_state([]),
                  report_paper={"holdings": holdings})
        # 10*(900-800) = +1,000
        assert r["summary"]["total_unrealized_pnl"] == 1_000
        assert r["summary"]["n_holdings"] == 1

    def test_no_report_returns_zero(self, tmp_path):
        r = _call(tmp_path, _build_state([]), report_paper={})
        assert r["summary"]["total_unrealized_pnl"] == 0
        assert r["summary"]["n_holdings"] == 0


class TestEdgeCases:
    def test_no_trades(self, tmp_path):
        r = _call(tmp_path, _build_state([]))
        assert r["summary"]["total_realized_pnl"] == 0
        assert r["summary"]["win_rate"] == 0
        assert r["summary"]["avg_win"] == 0
        assert r["summary"]["avg_loss"] == 0

    def test_split_trade_ignored(self, tmp_path):
        trades = [
            {"side": "split", "ticker": "6669.TW", "shares": 19,
             "price": None, "pnl_pct": None, "date": "2026-09-02"},
        ]
        r = _call(tmp_path, _build_state(trades))
        assert r["summary"]["n_sells"] == 0

    def test_returns_all_trades(self, tmp_path):
        trades = [
            {"side": "buy", "ticker": "X", "shares": 1, "price": 100,
             "pnl_pct": None, "date": "2026-01-01", "name": "X"},
            {"side": "sell", "ticker": "X", "shares": 1, "price": 110,
             "pnl_pct": 10.0, "date": "2026-04-01", "name": "X"},
        ]
        r = _call(tmp_path, _build_state(trades))
        assert len(r["trades"]) == 2
