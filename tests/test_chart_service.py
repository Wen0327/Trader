"""RotationService.ticker_series:mock 掉 Yahoo,離線驗證服務層組裝邏輯。

蓋掉先前只能手動 curl 的部分:白名單、intraday 序列格式、
日線疊加線/突破標記、快取鍵隔離。
"""

import pandas as pd
import pytest

from dashboard.api import RotationService


def _intraday_df(n: int = 3) -> pd.DataFrame:
    idx = pd.date_range("2026-07-13 01:00", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame({
        "open": [100.0 + i for i in range(n)],
        "high": [101.0 + i for i in range(n)],
        "low": [99.0 + i for i in range(n)],
        "close": [100.5 + i for i in range(n)],
        "volume": [10.0] * n,
    }, index=idx)


def _daily_df(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2026-04-01", periods=n, freq="D", tz="UTC")
    close = [100.0 + i for i in range(n)]  # 一路創高 → 尾端必為突破
    return pd.DataFrame({
        "open": close, "high": [c + 1 for c in close],
        "low": [c - 1 for c in close], "close": close,
        "volume": [10.0] * n,
    }, index=idx)


@pytest.fixture
def svc(monkeypatch):
    monkeypatch.setattr("data.yahoo_feed.fetch_intraday",
                        lambda ticker, interval: _intraday_df())
    monkeypatch.setattr("data.yahoo_feed.fetch_ohlcv",
                        lambda ticker, lookback_days=730: _daily_df())
    return RotationService()  # 新實例:不污染模組級單例的快取


class TestWhitelist:
    def test_unknown_ticker_rejected(self, svc):
        with pytest.raises(KeyError):
            svc.ticker_series("0000.TW", "5m")


class TestIntradaySeries:
    def test_series_shape(self, svc):
        r = svc.ticker_series("2330.TW", "5m")
        s = r["series"]
        assert len(s) == 3
        assert s[0]["date"] == "2026-07-13 01:00"  # UTC 含時分
        assert s[0]["open"] == 100.0 and s[0]["close"] == 100.5

    def test_no_daily_overlays(self, svc):
        # 200MA/55/20 是日線模型參照,分鐘級一律 None、breakout False
        s = svc.ticker_series("2330.TW", "5m")["series"]
        assert all(p["ma200"] is None and p["hi55"] is None
                   and p["lo20"] is None and p["breakout"] is False
                   for p in s)


class TestDailySeries:
    def test_overlays_and_breakout(self, svc):
        s = svc.ticker_series("2330.TW", "1d")["series"]
        assert s[0]["date"] == "2026-04-01"  # 日線不含時分
        last = s[-1]
        assert last["ma200"] is None  # 樣本不足 200 根 → 無 200MA
        assert last["hi55"] is not None and last["lo20"] is not None
        assert last["breakout"] is True  # 一路創高,收盤 > 前 55 日高


class TestCacheIsolation:
    def test_intervals_cached_separately(self, svc):
        five = svc.ticker_series("2330.TW", "5m")["series"]
        daily = svc.ticker_series("2330.TW", "1d")["series"]
        assert five[0]["date"] != daily[0]["date"]  # 5m 快取不得污染 1d

    def test_cache_hit_skips_fetch(self, svc, monkeypatch):
        svc.ticker_series("2330.TW", "5m")

        def boom(*a, **k):
            raise AssertionError("快取命中不應再打數據源")
        monkeypatch.setattr("data.yahoo_feed.fetch_intraday", boom)
        svc.ticker_series("2330.TW", "5m")  # 不拋 → 走快取
