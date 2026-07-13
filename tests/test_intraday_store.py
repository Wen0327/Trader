"""分鐘數據累積:merge_bars 重疊比對(append / 恆定比例重刻 / 非恆定衝突)。

設計依據:Yahoo 5m 只回溯 60 天,今天不存以後回填不了;
除權息後 Yahoo 整段重調 → 用重疊區實測調整因子重刻本地歷史,
非恆定差異(數據修正/髒數據)不自動動手。
"""

import pandas as pd
import pytest

from data.intraday_store import MergeResult, merge_bars


_ORIGIN = pd.Timestamp("2026-07-13 00:00", tz="UTC")


def _bars(start: str, n: int, scale: float = 1.0) -> pd.DataFrame:
    """值由「時間戳」決定(非序列位置):同一時刻在不同批次中值一致,
    才能正確模擬重疊區。scale 模擬 Yahoo 整段重調。"""
    idx = pd.date_range(start, periods=n, freq="5min", tz="UTC")
    val = [100.0 + (t - _ORIGIN).total_seconds() / 300 for t in idx]
    return pd.DataFrame({
        "open": [v * scale for v in val],
        "high": [(v + 0.5) * scale for v in val],
        "low": [(v - 0.5) * scale for v in val],
        "close": [(v + 0.25) * scale for v in val],
        "volume": [10.0] * n,
    }, index=idx)


class TestAppend:
    def test_empty_stored_takes_all_fresh(self):
        r = merge_bars(None, _bars("2026-07-13 01:00", 5))
        assert r.action == "append"
        assert len(r.merged) == 5

    def test_overlap_identical_appends_new_only(self):
        stored = _bars("2026-07-13 01:00", 10)
        fresh = _bars("2026-07-13 01:25", 10)  # 前 5 根重疊、後 5 根新
        r = merge_bars(stored, fresh)
        assert r.action == "append"
        assert len(r.merged) == 15  # 去重
        assert r.merged.index.is_monotonic_increasing

    def test_no_overlap_still_appends(self):
        stored = _bars("2026-07-13 01:00", 5)
        fresh = _bars("2026-07-14 01:00", 5)
        r = merge_bars(stored, fresh)
        assert r.action == "append"
        assert len(r.merged) == 10


class TestRescale:
    def test_constant_ratio_rescales_history(self):
        stored = _bars("2026-07-13 01:00", 10)
        # 除權息:Yahoo 新數據整段 × 0.98,含重疊區
        fresh = _bars("2026-07-13 01:25", 10, scale=0.98)
        r = merge_bars(stored, fresh)
        assert r.action == "rescaled"
        assert r.factor == pytest.approx(0.98, rel=1e-6)
        # 本地舊歷史(非重疊的第一根,01:00 → 值 112.25)也要被重刻
        assert r.merged["close"].iloc[0] == pytest.approx(112.25 * 0.98, rel=1e-6)
        assert len(r.merged) == 15

    def test_rescaled_volume_untouched(self):
        stored = _bars("2026-07-13 01:00", 10)
        fresh = _bars("2026-07-13 01:25", 10, scale=0.5)
        r = merge_bars(stored, fresh)
        assert r.action == "rescaled"
        assert r.merged["volume"].iloc[0] == 10.0  # 量不隨價格因子縮放


class TestConflict:
    def test_non_constant_diff_returns_conflict(self):
        stored = _bars("2026-07-13 01:00", 10)
        fresh = _bars("2026-07-13 01:25", 10)
        fresh.iloc[2, fresh.columns.get_loc("close")] *= 1.30  # 單根改值:非恆定
        r = merge_bars(stored, fresh)
        assert r.action == "conflict"
        # 衝突時不得動本地數據
        pd.testing.assert_frame_equal(r.merged, stored)

    def test_conflict_result_type(self):
        r = merge_bars(_bars("2026-07-13 01:00", 3), _bars("2026-07-13 01:00", 3))
        assert isinstance(r, MergeResult)
