"""加密貨幣恐懼貪婪指數(alternative.me,免費、無需 key)。

0 = 極度恐懼,100 = 極度貪婪。有 2018-02 至今完整歷史,
可隨時作為因子回測;未通過驗證前僅供顯示,不進交易決策。
"""

from __future__ import annotations

import requests

API_URL = "https://api.alternative.me/fng/"

LABELS = [
    (25, "極度恐懼"),
    (40, "恐懼"),
    (60, "中性"),
    (75, "貪婪"),
    (101, "極度貪婪"),
]


def classify(value: int) -> str:
    return next(label for cap, label in LABELS if value < cap)


def fetch_latest() -> dict | None:
    """回傳 {value, label} 或 None(失敗不拋例外)。"""
    try:
        r = requests.get(API_URL, params={"limit": 1}, timeout=10)
        r.raise_for_status()
        value = int(r.json()["data"][0]["value"])
        return {"value": value, "label": classify(value)}
    except Exception:
        return None
