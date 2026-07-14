"""分鐘數據累積:merge_bars 重疊比對(append / 恆定比例重刻 / 非恆定衝突)。

設計依據:Yahoo 5m 只回溯 60 天,今天不存以後回填不了;
除權息後 Yahoo 整段重調 → 用重疊區實測調整因子重刻本地歷史,
非恆定差異(數據修正/髒數據)不自動動手。
"""

import pandas as pd
import pytest

from data.intraday_store import MergeResult, drop_live_bar, merge_bars


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


class TestFloatNoise:
    """2026-07-14 事故:Yahoo 浮點抖動(~1e-6)被誤判成調整,
    每 6 小時重刻+轟炸 Discord。雜訊(≤1e-5)與真實除權息(≥1e-3)
    之間差百倍,容差 1e-3 乾淨切開。"""

    def test_tiny_jitter_is_append_not_rescale(self):
        stored = _bars("2026-07-13 01:00", 10)
        fresh = _bars("2026-07-13 01:25", 10, scale=1.000001)  # 浮點抖動
        r = merge_bars(stored, fresh)
        assert r.action == "append"
        assert len(r.merged) == 15


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

    def test_midwindow_exdiv_rescales_prefix_only(self):
        """除息日落在重疊窗中間:窗前段差恆定比例、後段一致。
        只重刻除息時點之前的歷史(含重疊窗之前的舊棒),之後的不動。"""
        stored = _bars("2026-07-13 01:00", 20)  # 01:00 ~ 02:35
        pre = _bars("2026-07-13 01:25", 10, scale=0.98)   # 01:25~02:10 已被重調
        post = _bars("2026-07-13 02:15", 10)              # 02:15 起(除息後)一致
        fresh = pd.concat([pre, post])
        r = merge_bars(stored, fresh)
        assert r.action == "rescaled"
        assert r.factor == pytest.approx(0.98, rel=1e-6)
        # 窗前歷史(01:00)重刻
        assert r.merged["close"].iloc[0] == pytest.approx(112.25 * 0.98, rel=1e-6)
        # 除息後(02:15,值 127.25)不動
        t = pd.Timestamp("2026-07-13 02:15", tz="UTC")
        assert r.merged.loc[t, "close"] == pytest.approx(127.25, rel=1e-9)


class TestHeal:
    def test_single_interior_mismatch_heals_with_fresh(self):
        """盤中存到未收完的活棒,之後 Yahoo 定稿值不同:
        少量(≤2)內部棒不一致 → 以定稿為準自癒,不得卡死成永久衝突。"""
        stored = _bars("2026-07-13 01:00", 10)
        stored.iloc[7, stored.columns.get_loc("close")] *= 1.03  # 活棒的暫存值
        fresh = _bars("2026-07-13 01:25", 10)  # 定稿
        r = merge_bars(stored, fresh)
        assert r.action == "healed"
        t = pd.Timestamp("2026-07-13 01:35", tz="UTC")  # 第 7 根
        # 以 fresh 定稿為準
        assert r.merged.loc[t, "close"] == pytest.approx(
            fresh.loc[t, "close"], rel=1e-9)

    def test_mismatch_touching_window_start_not_healed(self):
        """不一致含重疊窗第一根 → 窗外歷史很可能也需要重刻,
        不得用 heal 蒙混(會在窗界留下斷層)→ 走前綴重刻或衝突。"""
        stored = _bars("2026-07-13 01:00", 10)
        fresh = _bars("2026-07-13 01:25", 10)
        fresh.iloc[0, fresh.columns.get_loc("close")] *= 0.98  # 只有窗首differ
        r = merge_bars(stored, fresh)
        assert r.action != "healed"


class TestConflict:
    def test_scattered_non_constant_diff_returns_conflict(self):
        # 多根、比例不恆定、非前綴 → 數據修正/髒數據,不自動動手
        stored = _bars("2026-07-13 01:00", 10)
        fresh = _bars("2026-07-13 01:25", 10)
        # 重疊區 = fresh 的前 5 根(01:25~01:45);改 3 根、比例各異
        col = fresh.columns.get_loc("close")
        for i, f in ((1, 1.30), (2, 0.70), (3, 1.10)):
            fresh.iloc[i, col] *= f
        r = merge_bars(stored, fresh)
        assert r.action == "conflict"
        # 衝突時不得動本地數據
        pd.testing.assert_frame_equal(r.merged, stored)

    def test_conflict_result_type(self):
        r = merge_bars(_bars("2026-07-13 01:00", 3), _bars("2026-07-13 01:00", 3))
        assert isinstance(r, MergeResult)


class TestDropLiveBar:
    """從源頭不讓未收完的活棒進庫(台股 13:00 輪、美股台北凌晨輪都會中)。"""

    def test_unfinished_last_bar_dropped(self):
        df = _bars("2026-07-13 01:00", 5)  # 末根 01:20,收棒時刻 01:25
        now = pd.Timestamp("2026-07-13 01:23", tz="UTC")  # 還在走
        assert len(drop_live_bar(df, now=now)) == 4

    def test_finished_bars_kept(self):
        df = _bars("2026-07-13 01:00", 5)
        now = pd.Timestamp("2026-07-13 01:25", tz="UTC")  # 恰好收棒
        assert len(drop_live_bar(df, now=now)) == 5
