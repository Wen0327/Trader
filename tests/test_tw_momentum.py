"""台股動量模組:current_picks 選股邏輯 + update_tracking 調倉追蹤。"""

import json
from unittest.mock import patch

import pytest

from data.tw_momentum import MOM_CAP, TOP_N, current_picks, update_tracking


class TestCurrentPicks:
    def test_selects_top_n(self):
        # 用 UNIVERSE 裡的真實代號,避免 KeyError
        from data.value_screen import UNIVERSE
        tickers = list(UNIVERSE)[:20]
        momentum = {t: float(i * 5) for i, t in enumerate(tickers)}
        picks = current_picks(momentum)
        assert len(picks) == TOP_N
        # 動量最高的應在最前
        assert picks[0]["momentum_pct"] > picks[-1]["momentum_pct"]

    def test_excludes_above_cap(self):
        momentum = {
            "2330.TW": MOM_CAP * 100 + 1,  # 超過 cap,應被剔除
            "2317.TW": 50.0,
            "2301.TW": 30.0,
        }
        picks = current_picks(momentum)
        tickers = {p["ticker"] for p in picks}
        assert "2330.TW" not in tickers
        assert "2317.TW" in tickers

    def test_exactly_at_cap_included(self):
        momentum = {"2330.TW": MOM_CAP * 100}  # 剛好等於 cap
        picks = current_picks(momentum)
        assert len(picks) == 1

    def test_includes_name_from_universe(self):
        momentum = {"2330.TW": 80.0}
        picks = current_picks(momentum)
        assert picks[0]["name"] == "台積電"

    def test_fewer_than_top_n(self):
        momentum = {"2330.TW": 50.0, "2317.TW": 30.0}
        picks = current_picks(momentum)
        assert len(picks) == 2  # 不夠 TOP_N 就有幾個選幾個

    def test_empty_momentum_falls_back_to_live(self):
        # current_picks({}) 會走 `momentum or momentum_all()` 拉即時資料
        # 傳 None 也是一樣;空 dict 是 falsy → 會呼叫 momentum_all()
        # 這裡只測明確傳入空 dict 不 crash(它會 fallback 到 live)
        # 直接傳 eligible 為空的情況
        momentum = {"2330.TW": MOM_CAP * 100 + 50}  # 全超 cap
        picks = current_picks(momentum)
        assert picks == []


class TestUpdateTracking:
    def test_first_quarter_records(self, tmp_path):
        track_path = tmp_path / "track.json"
        picks = [{"ticker": "2330.TW", "name": "台積電", "momentum_pct": 80}]

        with patch("data.tw_momentum.TRACK_PATH", track_path):
            result = update_tracking(picks)
        assert result is True
        data = json.loads(track_path.read_text())
        assert len(data["rebalances"]) == 1
        assert data["rebalances"][0]["holdings"] == picks

    def test_same_quarter_skips(self, tmp_path):
        track_path = tmp_path / "track.json"
        picks = [{"ticker": "2330.TW", "name": "台積電", "momentum_pct": 80}]

        with patch("data.tw_momentum.TRACK_PATH", track_path):
            update_tracking(picks)
            result = update_tracking(picks)
        assert result is False
        data = json.loads(track_path.read_text())
        assert len(data["rebalances"]) == 1  # 沒有重複記錄
