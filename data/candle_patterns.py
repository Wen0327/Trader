"""K 線形態辨識(純顯示資訊)。

⚠️ 定位聲明:K 線形態的統計預測力在學術檢驗中普遍很弱,
此模組輸出僅作為通知與 UI 的描述性資訊,不得進入交易決策
(章程:未經驗證的因子不得參與交易)。

8 個經典形態,規則全部顯式定義(無魔法參數):
單根:長實體、十字星、鎚子、流星
雙根:多頭吞噬、空頭吞噬、內困(孕線)、外包
"""

from __future__ import annotations

import pandas as pd

BODY_LONG = 0.80    # 實體佔比 > 80% = 長實體
BODY_DOJI = 0.10    # 實體佔比 < 10% = 十字星
SHADOW_MULT = 2.0   # 長影線:> 實體 2 倍
SHORT_SHADOW = 0.10  # 短影線:< 區間 10%(不能用實體當基準 — 實體趨近 0 時會失效)


def _anatomy(o: float, h: float, l: float, c: float) -> dict:
    rng = (h - l) or 1e-9
    body = abs(c - o)
    return {
        "body_ratio": body / rng,
        "upper_shadow": h - max(o, c),
        "lower_shadow": min(o, c) - l,
        "body": body,
        "up": c >= o,
    }


def detect(df: pd.DataFrame) -> list[str]:
    """辨識最新一根(含與前一根的雙根形態),回傳形態名稱列表。"""
    if len(df) < 2:
        return []
    o, h, l, c = (float(df[k].iloc[-1]) for k in ("open", "high", "low", "close"))
    po, ph, pl, pc = (float(df[k].iloc[-2]) for k in ("open", "high", "low", "close"))
    a = _anatomy(o, h, l, c)
    patterns: list[str] = []

    # 單根
    if a["body_ratio"] > BODY_LONG:
        patterns.append("長實體" + ("陽" if a["up"] else "陰"))
    if a["body_ratio"] < BODY_DOJI:
        patterns.append("十字星")
    rng = (h - l) or 1e-9
    if a["lower_shadow"] > SHADOW_MULT * a["body"] and \
            a["upper_shadow"] < SHORT_SHADOW * rng:
        patterns.append("鎚子")
    if a["upper_shadow"] > SHADOW_MULT * a["body"] and \
            a["lower_shadow"] < SHORT_SHADOW * rng:
        patterns.append("流星")

    # 雙根
    prev_up = pc >= po
    if a["up"] and not prev_up and c > po and o < pc:
        patterns.append("多頭吞噬")
    if not a["up"] and prev_up and c < po and o > pc:
        patterns.append("空頭吞噬")
    if h < ph and l > pl:
        patterns.append("內困")
    if h > ph and l < pl:
        patterns.append("外包")

    return patterns
