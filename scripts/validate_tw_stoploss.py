"""台股動量停損 / 月頻調倉驗證:python scripts/validate_tw_stoploss.py

變體:
  A: 季調倉,無停損(現行)
  B: 季調倉 + 跌10%停損(現金閒置)
  C: 季調倉 + 跌15%停損
  D: 月調倉,無停損
  E: 月調倉 + 跌10%停損

停損規則:持倉自進場價跌超過 X% → 當日收盤賣出,現金閒置到下次調倉。
成本:0.4% × 每次進出事件(含停損賣出)。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf

from data.value_screen import UNIVERSE
from scripts.validate_tw_value import stats

START = "2010-01-01"
TOP_N = 10
COST = 0.004
MOM_CAP = 1.5


def run(ret, clean, mom, rebal_dates, stop_pct=None):
    """回測動量策略。

    rebal_dates: set of rebalance dates
    stop_pct: None=無停損, 0.10=跌10%停損
    """
    idx = ret.index
    port = pd.Series(0.0, index=idx)
    holdings: dict[str, float] = {}  # ticker -> entry_price

    for day in idx:
        # 當日報酬
        n_slots = max(len(holdings), 1)
        for t, entry in list(holdings.items()):
            port.loc[day] += ret.loc[day, t] / n_slots

        # 停損檢查
        if stop_pct and holdings:
            for t, entry in list(holdings.items()):
                px = clean.loc[day, t]
                if pd.notna(px) and px < entry * (1 - stop_pct):
                    port.loc[day] -= COST / n_slots
                    del holdings[t]

        # 調倉
        if day in rebal_dates:
            snap = mom.loc[day].dropna()
            snap = snap[snap <= MOM_CAP]
            new_set = set(snap.sort_values(ascending=False).head(TOP_N).index)
            if not new_set:
                continue

            # 賣出被踢的
            dropped = set(holdings) - new_set
            if dropped:
                exit_cost = COST * len(dropped) / max(len(new_set), 1)
                port.loc[day] -= exit_cost
                for t in dropped:
                    del holdings[t]

            # 買入新進的
            additions = new_set - set(holdings)
            if additions:
                entry_cost = COST * len(additions) / max(len(new_set), 1)
                port.loc[day] -= entry_cost
                for t in additions:
                    px = clean.loc[day, t]
                    if pd.notna(px):
                        holdings[t] = float(px)

    return port.loc[port.ne(0).idxmax():]


if __name__ == "__main__":
    tickers = list(UNIVERSE)
    data = yf.download(tickers + ["0050.TW"], start=START, auto_adjust=False,
                       actions=True, progress=False)
    adj = data["Adj Close"]
    ret = adj.pct_change().fillna(0.0)
    ret = ret.mask(ret.abs() > 0.11, 0.0)
    clean = (1 + ret).cumprod()
    clean = clean.mask(adj.isna())

    bench = ret["0050.TW"]
    ret = ret[tickers]
    clean = clean[tickers]

    mom = clean.shift(21) / clean.shift(252) - 1

    idx = adj.index
    q_ends = set(idx.to_series().groupby(idx.to_period("Q")).max().values)
    m_ends = set(idx.to_series().groupby(idx.to_period("M")).max().values)

    variants = {
        "A 季/無停損":    (q_ends, None),
        "B 季/停損10%":   (q_ends, 0.10),
        "C 季/停損15%":   (q_ends, 0.15),
        "D 月/無停損":    (m_ends, None),
        "E 月/停損10%":   (m_ends, 0.10),
    }

    print(f"{'變體':<14} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7}")
    start_idx = None
    for name, (dates, stop) in variants.items():
        p = run(ret, clean, mom, dates, stop)
        start_idx = start_idx or p.index[0]
        s = stats(p)
        print(f"{name:<14} {s['cagr']:>8.1%} {s['mdd']:>8.1%} {s['sharpe']:>7.2f}")

    sb = stats(bench.loc[start_idx:])
    print(f"{'0050 B&H':<14} {sb['cagr']:>8.1%} {sb['mdd']:>8.1%} {sb['sharpe']:>7.2f}")
    print("\n⚠️ 生存者偏差:以上為上限。停損 + 月頻會增加交易次數和成本。")
