"""策略訊號邏輯:暖機期、進出場條件、邊界。"""

import numpy as np
import pandas as pd

from strategy.cycle_short import CycleShort
from strategy.donchian import DonchianBreakout
from strategy.momentum import SmaCross
from strategy.regime import RegimeFilter


def make_ohlcv(closes, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq="D", tz="UTC")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1.0})


class TestDonchian:
    def test_warmup_is_flat(self):
        sig = DonchianBreakout(55, 20).generate_signals(make_ohlcv([100.0] * 60))
        assert (sig.iloc[:55] == 0).all()

    def test_breakout_enters_and_20low_exits(self):
        # 60 天平盤 → 突破 → 高位盤整 → 跌破 20 日低
        closes = [100.0] * 60 + [110.0] + [110.0] * 25 + [105.0]
        sig = DonchianBreakout(55, 20).generate_signals(make_ohlcv(closes))
        assert sig.iloc[60] == 1.0          # 突破 55 日高當天進場
        assert sig.iloc[70] == 1.0          # 持續持有
        assert sig.iloc[-1] == 0.0          # 跌破 20 日低(105 < 110)出場

    def test_flat_market_never_enters(self):
        sig = DonchianBreakout(55, 20).generate_signals(make_ohlcv([100.0] * 120))
        assert (sig == 0).all()


class TestRegime:
    def test_above_ma_long_below_flat(self):
        # 250 天緩漲(價格 > MA200)之後暴跌到 MA 之下
        closes = list(np.linspace(100, 200, 250)) + [50.0]
        sig = RegimeFilter(200).generate_signals(make_ohlcv(closes))
        assert sig.iloc[249] == 1.0
        assert sig.iloc[250] == 0.0

    def test_warmup_is_flat(self):
        sig = RegimeFilter(200).generate_signals(make_ohlcv([100.0] * 150))
        assert (sig == 0).all()


class TestSmaCross:
    def test_uptrend_long_downtrend_flat(self):
        up = list(np.linspace(100, 200, 100))
        down = list(np.linspace(200, 100, 100))
        sig = SmaCross(20, 60).generate_signals(make_ohlcv(up + down))
        assert sig.iloc[99] == 1.0    # 上升段尾:快線 > 慢線
        assert sig.iloc[-1] == 0.0    # 下降段尾:快線 < 慢線
        # 慢線在第 60 根(index 59)恰好形成 → 未形成的是 index 0~58
        assert (sig.iloc[:59] == 0).all()


class TestCycleShort:
    def _make(self, closes, start):
        return make_ohlcv(closes, start=start)

    def test_breakdown_in_window_enters_short(self):
        # 窗口:2020-05-11 減半 + 18~30 個月 = 2021-11-11 ~ 2022-11-11
        # 起始 2021-08-01,150 天平盤(建立 365 峰值 min_periods=100)後跌破 55 日低
        closes = [100.0] * 150 + [90.0]
        sig = CycleShort().generate_signals(self._make(closes, "2021-08-01"))
        assert sig.iloc[-1] == -1.0  # 2021-12-29 在窗口內,90 > 地板 50 → 開空

    def test_breakdown_outside_window_no_short(self):
        closes = [100.0] * 150 + [90.0]
        sig = CycleShort().generate_signals(self._make(closes, "2023-06-01"))
        assert (sig == 0).all()  # 2023 年底不在任何窗口

    def test_below_floor_blocks_entry(self):
        # 峰值 200 → 地板 100;跌破 55 日低時價格 90 < 地板 → 禁止開空
        closes = [200.0] * 120 + [110.0] * 30 + [90.0]
        sig = CycleShort().generate_signals(self._make(closes, "2021-08-01"))
        assert sig.iloc[-1] == 0.0

    def test_cover_on_20d_high_break(self):
        # 開空後反彈突破 20 日高 → 回補
        closes = [100.0] * 150 + [90.0] + [88.0] * 19 + [95.0]
        sig = CycleShort().generate_signals(self._make(closes, "2021-08-01"))
        assert sig.iloc[150] == -1.0   # 進空
        assert sig.iloc[-1] == 0.0     # 95 > 近20日高(88~90)→ 回補
