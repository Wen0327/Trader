"""台股紙上帳本:差額換倉、費用、損益記帳。"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from data.tw_paper import BUY_FEE, INITIAL_CASH, SELL_FEE, _adjust_splits, process


def picks(*tickers):
    return [{"ticker": t, "name": t, "momentum_pct": 50.0} for t in tickers]


class TestFirstRun:
    def test_buys_all_picks(self, tmp_path):
        path = tmp_path / "state.json"
        prices = {"2330.TW": 1000.0, "2317.TW": 200.0}
        out = process(picks("2330.TW", "2317.TW"), prices, False, state_path=path)
        assert len(out["holdings"]) == 2
        assert out["n_trades"] == 2
        # 現金 + 市值 ≈ 本金 − 買入費
        assert out["equity"] < INITIAL_CASH
        assert out["equity"] > INITIAL_CASH * (1 - BUY_FEE * 1.1)

    def test_integer_shares(self, tmp_path):
        path = tmp_path / "state.json"
        out = process(picks("2330.TW"), {"2330.TW": 999999.0}, False, state_path=path)
        assert out["holdings"] == []  # 買不起一股就不買


class TestDifferentialRebalance:
    def test_kept_name_is_not_churned(self, tmp_path):
        path = tmp_path / "state.json"
        prices = {"2330.TW": 1000.0, "2317.TW": 200.0}
        process(picks("2330.TW", "2317.TW"), prices, False, state_path=path)

        # 換倉:2330 留任、2317 被踢、2454 新進
        prices2 = {"2330.TW": 1100.0, "2317.TW": 210.0, "2454.TW": 500.0}
        out = process(picks("2330.TW", "2454.TW"), prices2, True, state_path=path)

        tickers = {h["ticker"] for h in out["holdings"]}
        assert tickers == {"2330.TW", "2454.TW"}
        # 留任的 2330 進場價不變(未被賣掉重買)
        kept = next(h for h in out["holdings"] if h["ticker"] == "2330.TW")
        assert kept["entry_price"] == 1000.0
        # 交易紀錄:首建 2 買 + 換倉 1 賣 1 買 = 4 筆(全賣全買會是 6 筆)
        assert out["n_trades"] == 4

    def test_sell_records_pnl_with_fees(self, tmp_path):
        path = tmp_path / "state.json"
        process(picks("2317.TW"), {"2317.TW": 100.0}, False, state_path=path)
        out = process(picks("2330.TW"),
                      {"2317.TW": 110.0, "2330.TW": 50.0}, True, state_path=path)
        sells = [t for t in
                 __import__("json").loads(path.read_text())["trades"]
                 if t["side"] == "sell"]
        assert sells[0]["pnl_pct"] == pytest.approx(10.0)  # 價差損益(費用另計於現金)

    def test_no_rebalance_between_quarters(self, tmp_path):
        path = tmp_path / "state.json"
        process(picks("2330.TW"), {"2330.TW": 1000.0}, False, state_path=path)
        out = process(picks("2454.TW"),  # 名單變了但季度未到
                      {"2330.TW": 1000.0, "2454.TW": 500.0}, False, state_path=path)
        assert {h["ticker"] for h in out["holdings"]} == {"2330.TW"}
        assert out["n_trades"] == 1  # 只有首建那筆


class TestValuation:
    def test_mark_to_market(self, tmp_path):
        path = tmp_path / "state.json"
        process(picks("2330.TW"), {"2330.TW": 1000.0}, False, state_path=path)
        out = process(picks("2330.TW"), {"2330.TW": 1200.0}, False, state_path=path)
        h = out["holdings"][0]
        assert h["pnl_pct"] == pytest.approx(20.0)
        assert out["equity"] > INITIAL_CASH  # +20% 遠大於買入費


class TestSplitAdjustment:
    @staticmethod
    def _fake_splits(ratio: float, split_date: str = "2026-09-02"):
        """Mock yf.Ticker(...).splits to return a single split."""
        idx = pd.DatetimeIndex([split_date], tz="Asia/Taipei")
        return pd.Series([ratio], index=idx, name="Stock Splits")

    def test_adjusts_shares_and_entry_price(self):
        state = {"positions": {
            "6669.TW": {"shares": 19, "entry_price": 5040.0,
                        "entry_date": "2026-07-10", "name": "緯穎"},
        }}
        with patch("data.tw_paper.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.splits = self._fake_splits(3.0)
            events = _adjust_splits(state)
        pos = state["positions"]["6669.TW"]
        assert pos["shares"] == 57  # 19 * 3
        assert pos["entry_price"] == pytest.approx(1680.0)  # 5040 / 3
        assert pos["last_split_adjusted"] == "2026-09-02"
        assert len(events) == 1

    def test_skips_already_adjusted(self):
        state = {"positions": {
            "6669.TW": {"shares": 57, "entry_price": 1680.0,
                        "entry_date": "2026-07-10", "name": "緯穎",
                        "last_split_adjusted": "2026-09-02"},
        }}
        with patch("data.tw_paper.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.splits = self._fake_splits(3.0)
            events = _adjust_splits(state)
        assert events == []
        assert state["positions"]["6669.TW"]["shares"] == 57  # 沒重複調整

    def test_no_split_no_change(self):
        state = {"positions": {
            "2330.TW": {"shares": 100, "entry_price": 1000.0,
                        "entry_date": "2026-07-10", "name": "台積電"},
        }}
        with patch("data.tw_paper.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.splits = pd.Series(
                dtype=float, name="Stock Splits")
            events = _adjust_splits(state)
        assert events == []
        assert state["positions"]["2330.TW"]["shares"] == 100

    def test_split_before_entry_ignored(self):
        state = {"positions": {
            "2330.TW": {"shares": 100, "entry_price": 500.0,
                        "entry_date": "2026-10-01", "name": "台積電"},
        }}
        with patch("data.tw_paper.yf.Ticker") as mock_ticker:
            # Split happened before entry
            mock_ticker.return_value.splits = self._fake_splits(2.0, "2026-08-01")
            events = _adjust_splits(state)
        assert events == []
        assert state["positions"]["2330.TW"]["shares"] == 100

    def test_double_call_no_double_adjust(self):
        """呼叫兩次 _adjust_splits 不應重複套用(防 process_d bug)。"""
        state = {"positions": {
            "6669.TW": {"shares": 19, "entry_price": 5040.0,
                        "entry_date": "2026-07-10", "name": "緯穎"},
        }}
        with patch("data.tw_paper.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.splits = self._fake_splits(3.0)
            _adjust_splits(state)
            _adjust_splits(state)  # 第二次不應有效果
        assert state["positions"]["6669.TW"]["shares"] == 57  # 不是 171

    def test_timezone_same_day_not_reapplied(self):
        """split 時間 09:00+08:00 vs last_adj 日期 00:00 不應重入。"""
        state = {"positions": {
            "2885.TW": {"shares": 1520, "entry_price": 65.67,
                        "entry_date": "2026-07-10", "name": "元大金",
                        "last_split_adjusted": "2026-08-18"},
        }}
        # 模擬 yfinance 回傳帶時區的 split(09:00+08:00)
        idx = pd.DatetimeIndex(["2026-08-18 09:00:00"], tz="Asia/Taipei")
        splits = pd.Series([1.04], index=idx, name="Stock Splits")
        with patch("data.tw_paper.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.splits = splits
            events = _adjust_splits(state)
        assert events == []
        assert state["positions"]["2885.TW"]["shares"] == 1520  # 沒被重複調整

    def test_multiple_splits_cumulative(self):
        """同一持倉有多次分割應累乘。"""
        state = {"positions": {
            "TEST.TW": {"shares": 100, "entry_price": 1000.0,
                        "entry_date": "2026-01-01", "name": "測試"},
        }}
        idx = pd.DatetimeIndex(["2026-03-01", "2026-06-01"], tz="Asia/Taipei")
        splits = pd.Series([2.0, 1.5], index=idx, name="Stock Splits")
        with patch("data.tw_paper.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.splits = splits
            events = _adjust_splits(state)
        # 100 * 2.0 * 1.5 = 300
        assert state["positions"]["TEST.TW"]["shares"] == 300
        assert state["positions"]["TEST.TW"]["entry_price"] == pytest.approx(333.33, abs=0.01)
        assert state["positions"]["TEST.TW"]["last_split_adjusted"] == "2026-06-01"

    def test_process_d_does_not_double_adjust(self, tmp_path):
        """process_d 呼叫 _adjust_splits + 內部 process 再呼叫,不應重複。"""
        path = tmp_path / "d.json"
        # 建倉:手動寫 state 控制 entry_date(避免依賴 datetime.now)
        first_buy = int(INITIAL_CASH // (1000 * (1 + BUY_FEE)))
        state = {
            "cash": INITIAL_CASH - first_buy * 1000 * (1 + BUY_FEE),
            "positions": {
                "2330.TW": {"shares": first_buy, "entry_price": 1000.0,
                            "entry_date": "2026-07-10", "name": "台積電"},
            },
            "started": "2026-07-10", "trades": [],
            "reserve_cash": 0.0, "exp_state": "normal",
        }
        path.write_text(json.dumps(state))

        # split 在建倉之後:process_d + 內部 process 各呼叫一次 _adjust_splits
        splits_data = self._fake_splits(2.0, "2026-09-15")
        with patch("data.tw_paper.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.splits = splits_data
            from data.tw_paper import process_d
            process_d(picks("2330.TW"), {"2330.TW": 500.0}, False,
                      state_path=path,
                      signal={"below_ma200": False, "dd_52w": -0.02})

        final = json.loads(path.read_text())
        pos = final["positions"]["2330.TW"]
        assert pos["shares"] == first_buy * 2  # 一次分割 ×2
        assert pos["shares"] < first_buy * 4   # 沒有雙重套用 ×4