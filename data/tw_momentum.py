"""台股截面動量:前瞻追蹤(不動錢的真實樣本外驗證)。

背景:回測 2010-2026 大勝 0050(鄰域 12/12、雙子區段皆勝),
但生存者偏差無法以免費數據量化 → 以前瞻紀錄累積真實樣本外證據。
規則與回測一致:12-1 月動量 TOP10、季調倉、等權。
每季第一次執行時記錄調倉快照,對帳時以快照重算實際績效 vs 0050。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

from data.value_screen import UNIVERSE

TRACK_PATH = Path(__file__).resolve().parent.parent / "storage" / "tw_momentum_track.json"
LOOKBACK, SKIP, TOP_N = 252, 21, 10
REBALANCE_COST = 0.004
# 極端動量剔除(M5,2026-07-10 採用):12-1 動量 > 150% 不選。
# 驗證:回撤 -40.6%→-37.7%、Sharpe 1.22→1.28,鄰域 100~500% 全域不傷;
# 高 cap(≥250%)無回撤改善 → 150% 是對治動量崩潰的對症劑量。
MOM_CAP = 1.5


def _clean_returns(adj: pd.DataFrame) -> pd.DataFrame:
    ret = adj.pct_change().fillna(0.0)
    return ret.mask(ret.abs() > 0.11, 0.0)  # 台股漲跌停清洗


def momentum_all() -> dict[str, float]:
    """全池 12-1 動量(%),供表格排序與 TOP10 選取。"""
    tickers = list(UNIVERSE)
    adj = yf.download(tickers, period="2y", auto_adjust=True,
                      progress=False)["Close"]
    clean = (1 + _clean_returns(adj)).cumprod()
    momentum = (clean.shift(SKIP) / clean.shift(LOOKBACK) - 1).iloc[-1].dropna()
    return {t: round(float(m) * 100, 1) for t, m in momentum.items()}


def current_picks(momentum: dict[str, float] | None = None) -> list[dict]:
    momentum = momentum or momentum_all()
    eligible = {t: m for t, m in momentum.items() if m <= MOM_CAP * 100}
    top = sorted(eligible.items(), key=lambda kv: -kv[1])[:TOP_N]
    return [
        {"ticker": t, "name": UNIVERSE[t], "momentum_pct": m}
        for t, m in top
    ]


def update_tracking(picks: list[dict]) -> bool:
    """每季第一次執行記錄調倉快照。回傳是否為新調倉。"""
    quarter = str(pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("Q"))
    track = {"rebalances": []}
    if TRACK_PATH.exists():
        track = json.loads(TRACK_PATH.read_text())
    if track["rebalances"] and track["rebalances"][-1]["quarter"] == quarter:
        return False
    track["rebalances"].append({
        "quarter": quarter,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "holdings": picks,
    })
    TRACK_PATH.parent.mkdir(exist_ok=True)
    TRACK_PATH.write_text(json.dumps(track, ensure_ascii=False, indent=1))
    return True


# 歷史狀態分桶統計(2010-2026 回測,2026-07-10 計算;M5-150 規則)
# 桶 = 0050 近12月報酬四分位;值 = (下一季平均報酬%, 勝率%)
HEAT_BUCKETS = [
    (0.03, "冷", 10.1, 81),     # 12月報酬 < +3%
    (0.135, "溫", 5.8, 73),     # +3% ~ +13%
    (0.275, "熱", 4.6, 67),     # +14% ~ +27%
    (float("inf"), "極熱", 11.9, 75),  # > +28%
]
REGIME_STATS = {True: (8.5, 80), False: (6.9, 54)}  # 0050 vs 200MA


def market_state() -> dict | None:
    """今日市場狀態 + 歷史同狀態的下一季統計(供週報一行摘要)。"""
    try:
        b50 = yf.download("0050.TW", period="2y", auto_adjust=True,
                          progress=False)["Close"]
        if isinstance(b50, pd.DataFrame):
            b50 = b50.iloc[:, 0]
        ret = b50.pct_change()
        b50 = (1 + ret.mask(ret.abs() > 0.11, 0.0).fillna(0.0)).cumprod() * float(b50.iloc[0])
        ma200 = b50.rolling(200).mean().iloc[-1]
        heat = float(b50.iloc[-1] / b50.iloc[-252] - 1)
        regime_on = bool(b50.iloc[-1] > ma200)
        bucket = next(b for b in HEAT_BUCKETS if heat < b[0])
        r_avg, r_win = REGIME_STATS[regime_on]
        return {
            "regime_on": regime_on,
            "pct_vs_ma200": round(float(b50.iloc[-1] / ma200 - 1) * 100, 1),
            "heat_12m_pct": round(heat * 100, 0),
            "bucket": bucket[1],
            "bucket_next_q_avg": bucket[2],
            "bucket_win_rate": bucket[3],
            "regime_next_q_avg": r_avg,
            "regime_win_rate": r_win,
        }
    except Exception:
        return None


def forward_performance() -> dict | None:
    """以歷史快照重算前瞻績效(等權、季調倉、含成本)vs 0050。"""
    if not TRACK_PATH.exists():
        return None
    rebalances = json.loads(TRACK_PATH.read_text())["rebalances"]
    if not rebalances:
        return None

    start = rebalances[0]["date"]
    all_tickers = sorted({h["ticker"] for r in rebalances for h in r["holdings"]})
    adj = yf.download(all_tickers + ["0050.TW"], start=start,
                      auto_adjust=True, progress=False)["Close"]
    ret = _clean_returns(adj)

    strat = 1.0
    for i, r in enumerate(rebalances):
        d0 = r["date"]
        d1 = rebalances[i + 1]["date"] if i + 1 < len(rebalances) else None
        seg = ret.loc[d0:d1, [h["ticker"] for h in r["holdings"]]]
        if len(seg) > 1:
            period_ret = float((1 + seg.iloc[1:].mean(axis=1)).prod() - 1)
            strat *= (1 + period_ret) * (1 - REBALANCE_COST)

    bench_ret = ret["0050.TW"]
    bench = float((1 + bench_ret.iloc[1:]).prod())
    return {
        "since": start,
        "n_rebalances": len(rebalances),
        "strategy_pct": round((strat - 1) * 100, 1),
        "bench_0050_pct": round((bench - 1) * 100, 1),
    }
