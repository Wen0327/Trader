"""持倉狀態:存讀往返、空單負數量、路徑隔離。"""

from execution.portfolio import Portfolio


class TestPortfolio:
    def test_roundtrip(self, tmp_path):
        path = tmp_path / "state.json"
        p = Portfolio.load(path)
        p.set("BTC/USDT", 0.5, 60_000.0)
        p.risk_state = {"day": "2026-07-09", "killed": False}
        p.save()

        loaded = Portfolio.load(path)
        assert loaded.get("BTC/USDT").amount == 0.5
        assert loaded.get("BTC/USDT").entry_price == 60_000.0
        assert loaded.risk_state["day"] == "2026-07-09"

    def test_short_negative_amount_survives_save(self, tmp_path):
        path = tmp_path / "state.json"
        p = Portfolio.load(path)
        p.set("BTC/USDT:USDT", -0.01, 62_000.0)
        p.save()
        assert Portfolio.load(path).get("BTC/USDT:USDT").amount == -0.01

    def test_clear_removes_position(self, tmp_path):
        path = tmp_path / "state.json"
        p = Portfolio.load(path)
        p.set("ETH/USDT", 1.0, 1_800.0)
        p.clear("ETH/USDT")
        p.save()
        assert Portfolio.load(path).get("ETH/USDT").amount == 0.0

    def test_missing_file_returns_empty(self, tmp_path):
        p = Portfolio.load(tmp_path / "nope.json")
        assert p.positions == {}
        assert p.get("BTC/USDT").amount == 0.0
