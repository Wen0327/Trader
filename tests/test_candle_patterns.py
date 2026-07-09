"""K 線形態辨識:每個形態的合成 OHLC 精確案例。"""

import pandas as pd

from data.candle_patterns import detect


def bars(*rows):
    """rows: (open, high, low, close)"""
    return pd.DataFrame(
        [dict(zip(("open", "high", "low", "close"), r)) for r in rows])


class TestSingleBar:
    def test_long_bull_body(self):
        assert "長實體陽" in detect(bars((100, 110, 100, 100), (100, 110, 99.5, 109.5)))

    def test_doji(self):
        assert "十字星" in detect(bars((100, 110, 100, 105), (105, 110, 100, 105.3)))

    def test_hammer(self):
        # 長下影(7)、小實體(1)、極短上影(0.5,< 區間10%)
        assert "鎚子" in detect(bars((100, 110, 100, 105), (109, 110.5, 102, 110)))

    def test_doji_hammer(self):
        # 實體趨近 0 的十字鎚 — 舊規則(影線<實體)下永遠不成立的案例
        assert "鎚子" in detect(bars((100, 110, 100, 105), (110, 110.2, 102, 110)))

    def test_shooting_star(self):
        # 長上影(8)、小實體(2)、無下影
        assert "流星" in detect(bars((100, 110, 100, 105), (102, 110, 101.5, 102.5)))


class TestTwoBar:
    def test_bullish_engulfing(self):
        # 前陰(105→102),今陽實體完全包住(101→106)
        assert "多頭吞噬" in detect(bars((105, 106, 101, 102), (101, 107, 100, 106)))

    def test_bearish_engulfing(self):
        assert "空頭吞噬" in detect(bars((102, 106, 101, 105), (106, 107, 100, 101)))

    def test_inside_bar(self):
        assert "內困" in detect(bars((100, 110, 95, 105), (103, 107, 99, 104)))

    def test_outside_bar(self):
        assert "外包" in detect(bars((100, 106, 99, 105), (98, 110, 95, 108)))


class TestEdges:
    def test_single_row_returns_empty(self):
        assert detect(bars((100, 110, 100, 105))) == []

    def test_plain_bar_no_patterns(self):
        # 普通中等實體、雙邊短影、非吞噬非內外包
        out = detect(bars((100, 108, 98, 104), (103, 109, 101, 106)))
        assert out == []
