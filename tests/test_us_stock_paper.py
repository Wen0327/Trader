"""US 個股帳:基準不追、新觸發才買、滿倉上限、訊號死亡即賣。"""

import json

from data.us_stock_paper import MAX_POSITIONS, process


def w(ticker, rank, edge=True, price=100.0):
    return {"ticker": ticker, "label": ticker, "status_rank": rank,
            "edge_passed": edge, "price": price}


class TestBaseline:
    def test_first_run_does_not_chase_existing_signals(self, tmp_path):
        path = tmp_path / "us.json"
        out = process([w("TAN", 4), w("ZM", 2)], state_path=path)
        assert out["holdings"] == []          # TAN 已在訊號中 → 列基準,不追
        assert "TAN" in json.loads(path.read_text())["seen_active"]

    def test_new_trigger_buys(self, tmp_path):
        path = tmp_path / "us.json"
        process([w("TAN", 2), w("ZM", 2)], state_path=path)   # 基準:無人觸發
        out = process([w("TAN", 4), w("ZM", 2)], state_path=path)  # TAN 新觸發
        assert len(out["holdings"]) == 1
        assert out["holdings"][0]["ticker"] == "TAN"

    def test_edge_failed_never_trades(self, tmp_path):
        path = tmp_path / "us.json"
        process([w("XX", 2, edge=False)], state_path=path)
        out = process([w("XX", 4, edge=False)], state_path=path)  # 觸發但無 edge
        assert out["holdings"] == []


class TestLifecycle:
    def test_signal_death_sells_with_pnl(self, tmp_path):
        path = tmp_path / "us.json"
        process([w("TAN", 2)], state_path=path)
        process([w("TAN", 4, price=100.0)], state_path=path)   # 觸發買進
        out = process([w("TAN", 2, price=110.0)], state_path=path)  # 訊號死亡
        assert out["holdings"] == []
        sells = [t for t in json.loads(path.read_text())["trades"]
                 if t["side"] == "sell"]
        assert len(sells) == 1
        assert sells[0]["pnl_pct"] > 8  # ~+10% 減滑價

    def test_max_positions_cap(self, tmp_path):
        path = tmp_path / "us.json"
        names = [f"S{i}" for i in range(6)]
        process([w(n, 2) for n in names], state_path=path)          # 基準
        out = process([w(n, 4) for n in names], state_path=path)    # 六檔同日觸發
        assert len(out["holdings"]) == MAX_POSITIONS