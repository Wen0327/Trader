"""Shioaji 即時數據:快照報價。全 mock,不打真實 API。"""

from unittest.mock import MagicMock, patch

import pytest

from data.shioaji_feed import ShioajiFeed


def _mock_snapshot(code: str, close: float, volume: int = 1000):
    s = MagicMock()
    s.code = code
    s.close = close
    s.total_volume = volume
    s.ts = 1791280748587710000
    return s


class TestFetchQuotes:
    def test_returns_price_dict(self):
        with patch("data.shioaji_feed.sj") as mock_sj:
            api = MagicMock()
            mock_sj.Shioaji.return_value = api
            api.contracts.get.side_effect = lambda c: MagicMock(code=c)
            api.snapshots.return_value = [
                _mock_snapshot("2330", 580.0),
                _mock_snapshot("2317", 245.5),
            ]
            feed = ShioajiFeed(api_key="k", secret_key="s")
            quotes = feed.fetch_quotes(["2330.TW", "2317.TW"])

        assert quotes["2330.TW"]["price"] == 580.0
        assert quotes["2317.TW"]["price"] == 245.5

    def test_includes_volume(self):
        with patch("data.shioaji_feed.sj") as mock_sj:
            api = MagicMock()
            mock_sj.Shioaji.return_value = api
            api.contracts.get.side_effect = lambda c: MagicMock(code=c)
            api.snapshots.return_value = [
                _mock_snapshot("2330", 580.0, volume=5000),
            ]
            feed = ShioajiFeed(api_key="k", secret_key="s")
            quotes = feed.fetch_quotes(["2330.TW"])

        assert quotes["2330.TW"]["volume"] == 5000

    def test_skips_unknown_contract(self):
        with patch("data.shioaji_feed.sj") as mock_sj:
            api = MagicMock()
            mock_sj.Shioaji.return_value = api
            api.contracts.get.side_effect = lambda c: None if c == "FAKE" else MagicMock(code=c)
            api.snapshots.return_value = [
                _mock_snapshot("2330", 580.0),
            ]
            feed = ShioajiFeed(api_key="k", secret_key="s")
            quotes = feed.fetch_quotes(["2330.TW", "FAKE.TW"])

        assert "2330.TW" in quotes
        assert "FAKE.TW" not in quotes

    def test_empty_tickers(self):
        with patch("data.shioaji_feed.sj") as mock_sj:
            api = MagicMock()
            mock_sj.Shioaji.return_value = api
            feed = ShioajiFeed(api_key="k", secret_key="s")
            quotes = feed.fetch_quotes([])

        assert quotes == {}

    def test_strips_tw_suffix(self):
        """確認 .TW / .TWO 後綴被正確剝離再查 contract。"""
        with patch("data.shioaji_feed.sj") as mock_sj:
            api = MagicMock()
            mock_sj.Shioaji.return_value = api
            api.contracts.get.side_effect = lambda c: MagicMock(code=c)
            api.snapshots.return_value = [
                _mock_snapshot("3529", 800.0),
            ]
            feed = ShioajiFeed(api_key="k", secret_key="s")
            quotes = feed.fetch_quotes(["3529.TWO"])

        api.contracts.get.assert_called_with("3529")
        assert "3529.TWO" in quotes


class TestSessionManagement:
    def test_lazy_login(self):
        """建構時登入一次，之後共用 session。"""
        with patch("data.shioaji_feed.sj") as mock_sj:
            api = MagicMock()
            mock_sj.Shioaji.return_value = api
            feed = ShioajiFeed(api_key="k", secret_key="s")

        api.login.assert_called_once_with(api_key="k", secret_key="s")

    def test_logout(self):
        with patch("data.shioaji_feed.sj") as mock_sj:
            api = MagicMock()
            mock_sj.Shioaji.return_value = api
            feed = ShioajiFeed(api_key="k", secret_key="s")
            feed.logout()

        api.logout.assert_called_once()
