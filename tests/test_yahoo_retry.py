"""Yahoo 批量下載重試:2026-07-13 台股週掃因 Yahoo 暫時斷線
78 檔全數失敗而 crash(週更任務 → 沉默爛一週)。重試邏輯堵住此洞。"""

import pandas as pd
import pytest

from data.yahoo_feed import retry_download


def _good():
    return pd.DataFrame({"2330.TW": [100.0, 101.0]})


def _empty():
    return pd.DataFrame({"2330.TW": [float("nan"), float("nan")]})


class TestRetryDownload:
    def test_success_first_try_no_retry(self, monkeypatch):
        calls = []
        monkeypatch.setattr("data.yahoo_feed.time.sleep",
                            lambda s: calls.append(s))
        n = [0]

        def fetch():
            n[0] += 1
            return _good()

        df = retry_download(fetch, attempts=3, delay_sec=60)
        assert n[0] == 1 and calls == []  # 成功不重試、不等待
        assert not df.dropna(how="all").empty

    def test_transient_failure_recovers(self, monkeypatch):
        slept = []
        monkeypatch.setattr("data.yahoo_feed.time.sleep", slept.append)
        results = [_empty(), _empty(), _good()]

        df = retry_download(lambda: results.pop(0), attempts=3, delay_sec=60)
        assert not df.dropna(how="all").empty  # 第三次成功
        assert slept == [60, 60]

    def test_all_attempts_fail_raises(self, monkeypatch):
        monkeypatch.setattr("data.yahoo_feed.time.sleep", lambda s: None)
        n = [0]

        def fetch():
            n[0] += 1
            return _empty()

        with pytest.raises(RuntimeError, match="全數失敗"):
            retry_download(fetch, attempts=3, delay_sec=60)
        assert n[0] == 3  # 重試次數確實用滿

    def test_partial_data_counts_as_success(self, monkeypatch):
        # 部分股票失敗屬正常(下市、停牌),不觸發重試
        monkeypatch.setattr("data.yahoo_feed.time.sleep", lambda s: None)
        mixed = pd.DataFrame({"2330.TW": [100.0], "0000.TW": [float("nan")]})
        df = retry_download(lambda: mixed, attempts=3, delay_sec=60)
        assert list(df.columns) == ["2330.TW", "0000.TW"]
