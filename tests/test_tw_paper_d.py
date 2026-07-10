"""D 帳狀態機:騰金/部署/回補、預備金隔離、加權進場價。"""

import json

import pytest

from data.tw_paper import process, process_d

BULL = {"below_ma200": False, "dd_52w": -0.02}
BEAR_SHALLOW = {"below_ma200": True, "dd_52w": -0.12}
BEAR_DEEP = {"below_ma200": True, "dd_52w": -0.22}


def picks(*tickers):
    return [{"ticker": t, "name": t, "momentum_pct": 50.0} for t in tickers]


def seed(path, prices):
    """先用 A 邏輯建倉(D 帳與 A 帳共用建倉路徑)。"""
    return process_d(picks(*prices), prices, False, state_path=path, signal=BULL)


class TestReserve:
    def test_below_ma_raises_reserve(self, tmp_path):
        path = tmp_path / "d.json"
        prices = {"2330.TW": 100.0, "2317.TW": 50.0}
        seed(path, prices)
        out = process_d(picks(*prices), prices, False, state_path=path,
                        signal=BEAR_SHALLOW)
        assert out["exp_state"] == "reserved"
        assert out["reserve_cash"] > 0
        state = json.loads(path.read_text())
        sells = [t for t in state["trades"] if t.get("note") == "騰預備金"]
        assert len(sells) == 2  # 兩檔各賣一部分

    def test_reserve_roughly_quarter(self, tmp_path):
        path = tmp_path / "d.json"
        prices = {"2330.TW": 100.0}
        before = seed(path, prices)
        out = process_d(picks("2330.TW"), prices, False, state_path=path,
                        signal=BEAR_SHALLOW)
        # 預備金 ≈ 賣出 25% 持倉的淨額(整股+費用造成小誤差)
        assert out["reserve_cash"] == pytest.approx(before["equity"] * 0.25, rel=0.06)

    def test_no_double_reserve(self, tmp_path):
        path = tmp_path / "d.json"
        prices = {"2330.TW": 100.0}
        seed(path, prices)
        process_d(picks("2330.TW"), prices, False, state_path=path, signal=BEAR_SHALLOW)
        r1 = json.loads(path.read_text())["reserve_cash"]
        process_d(picks("2330.TW"), prices, False, state_path=path, signal=BEAR_SHALLOW)
        r2 = json.loads(path.read_text())["reserve_cash"]
        assert r1 == r2  # reserved 狀態下不再重複騰金


class TestDeploy:
    def test_panic_deploy_at_dd20(self, tmp_path):
        path = tmp_path / "d.json"
        prices = {"2330.TW": 100.0}
        seed(path, prices)
        process_d(picks("2330.TW"), prices, False, state_path=path, signal=BEAR_SHALLOW)
        cheap = {"2330.TW": 80.0}  # 恐慌價
        out = process_d(picks("2330.TW"), cheap, False, state_path=path,
                        signal=BEAR_DEEP)
        assert out["exp_state"] == "deployed"
        assert out["reserve_cash"] == 0
        state = json.loads(path.read_text())
        deploys = [t for t in state["trades"] if t.get("note") == "恐慌部署"]
        assert len(deploys) == 1
        # 加權進場價:原 100 進、部分 80 加碼 → 介於 80~100
        ep = state["positions"]["2330.TW"]["entry_price"]
        assert 80.0 < ep < 100.0

    def test_fallback_redeploys_on_ma_reclaim(self, tmp_path):
        path = tmp_path / "d.json"
        prices = {"2330.TW": 100.0}
        seed(path, prices)
        process_d(picks("2330.TW"), prices, False, state_path=path, signal=BEAR_SHALLOW)
        out = process_d(picks("2330.TW"), prices, False, state_path=path, signal=BULL)
        assert out["exp_state"] == "normal"
        assert out["reserve_cash"] == 0


class TestReserveSegregation:
    def test_rebalance_cannot_spend_reserve(self, tmp_path):
        path = tmp_path / "d.json"
        prices = {"2330.TW": 100.0}
        seed(path, prices)
        process_d(picks("2330.TW"), prices, False, state_path=path, signal=BEAR_SHALLOW)
        reserve = json.loads(path.read_text())["reserve_cash"]
        # 季調倉換股:新進股只能用自由現金買,預備金不動
        prices2 = {"2330.TW": 100.0, "2454.TW": 50.0}
        out = process_d(picks("2454.TW"), prices2, True, state_path=path,
                        signal=BEAR_SHALLOW)
        assert out["reserve_cash"] == pytest.approx(reserve, abs=1.0)  # 輸出取整