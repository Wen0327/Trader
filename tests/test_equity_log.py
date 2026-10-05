"""權益快照 JSONL:寫入、讀取、軌道過濾。"""

import json
from unittest.mock import patch

from monitoring.equity_log import read, record


class TestRecord:
    def test_appends_jsonl(self, tmp_path):
        path = tmp_path / "equity.jsonl"
        with patch("monitoring.equity_log.PATH", path):
            record("spot", 10000.123)
            record("paper_tw", 1050000)
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2
        row = json.loads(lines[0])
        assert row["track"] == "spot"
        assert row["equity"] == 10000.12  # round(10000.123, 2)

    def test_rounds_to_two_decimals(self, tmp_path):
        path = tmp_path / "equity.jsonl"
        with patch("monitoring.equity_log.PATH", path):
            record("x", 99.999)
        row = json.loads(path.read_text().strip())
        assert row["equity"] == 100.0


class TestRead:
    def test_filters_by_track(self, tmp_path):
        path = tmp_path / "equity.jsonl"
        with patch("monitoring.equity_log.PATH", path):
            record("spot", 100)
            record("paper_tw", 200)
            record("spot", 110)
            result = read("spot")
        assert len(result) == 2
        assert result[0]["equity"] == 100
        assert result[1]["equity"] == 110

    def test_empty_file(self, tmp_path):
        path = tmp_path / "equity.jsonl"
        path.write_text("")
        with patch("monitoring.equity_log.PATH", path):
            assert read("spot") == []

    def test_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.jsonl"
        with patch("monitoring.equity_log.PATH", path):
            assert read("spot") == []

    def test_corrupted_line_skipped(self, tmp_path):
        path = tmp_path / "equity.jsonl"
        with patch("monitoring.equity_log.PATH", path):
            record("spot", 100)
        # 插入一行壞資料
        with path.open("a") as f:
            f.write("not json\n")
        with patch("monitoring.equity_log.PATH", path):
            record("spot", 200)
        with patch("monitoring.equity_log.PATH", path):
            result = read("spot")
        assert len(result) == 2  # 壞行被跳過
