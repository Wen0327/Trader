"""K 線多時間框:4h 重採樣(Yahoo 無原生 4h,由 1h 合成)與 interval 表。"""

import pandas as pd
import pytest

from data.yahoo_feed import INTRADAY_PERIOD, resample_4h


def _hourly(n: int) -> pd.DataFrame:
    idx = pd.date_range("2026-07-13 00:00", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({
        "open": [100.0 + i for i in range(n)],
        "high": [101.0 + i for i in range(n)],
        "low": [99.0 + i for i in range(n)],
        "close": [100.5 + i for i in range(n)],
        "volume": [10.0] * n,
    }, index=idx)


class TestResample4h:
    def test_ohlcv_semantics(self):
        # 8 根 1h → 2 根 4h:open 取首、high 取最大、low 取最小、close 取尾、volume 加總
        out = resample_4h(_hourly(8))
        assert len(out) == 2
        first = out.iloc[0]
        assert first["open"] == 100.0   # 第 0 根的 open
        assert first["high"] == 104.0   # 第 3 根的 high
        assert first["low"] == 99.0     # 第 0 根的 low
        assert first["close"] == 103.5  # 第 3 根的 close
        assert first["volume"] == 40.0

    def test_partial_bucket_kept(self):
        # 尾端不足 4 根也要保留(最新未完成 K 棒)
        out = resample_4h(_hourly(6))
        assert len(out) == 2
        assert out.iloc[1]["close"] == 105.5  # 第 5 根的 close

    def test_empty_gap_dropped(self):
        # 休市時段(整段無資料)不得產生空 K 棒
        df = pd.concat([_hourly(4), _hourly(4).shift(freq="12h")])
        out = resample_4h(df)
        assert len(out) == 2  # 中間 8 小時空檔不補棒


class TestIntervalTable:
    def test_supported_intervals(self):
        assert set(INTRADAY_PERIOD) == {"5m", "15m", "30m", "1h", "4h"}

    def test_periods_within_yahoo_limits(self):
        # Yahoo 限制:分鐘級最多 60 天、1h 最多 730 天
        assert INTRADAY_PERIOD["5m"] == "5d"
        assert INTRADAY_PERIOD["15m"] == "1mo"
        assert INTRADAY_PERIOD["30m"] == "1mo"
        assert INTRADAY_PERIOD["1h"] == "3mo"
        assert INTRADAY_PERIOD["4h"] == "6mo"
