"""台股動量風控疊加驗證:python scripts/validate_tw_momentum_risk.py

對治「動量崩潰」(使用者提出:選中股皆已漲數輪,追高風險)的三個變體:
  M3 反波動率加權:TOP10 權重 ∝ 1/60日波動(拋物線股自動輕倉)
  M4 個股移動出場:季中跌破自身20日低 → 該席位轉現金至下次調倉
  M5 極端動量剔除:12-1 動量 > 150% / 300% 者不選(「別追」的字面版)
基準:M1 等權(原版)、0050。同窗口、同清洗、成本按換手。
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

if __name__ == "__main__":
    tickers = list(UNIVERSE)
    data = yf.download(tickers + ["0050.TW"], start=START, auto_adjust=False,
                       actions=True, progress=False)
    adj = data["Adj Close"]
    ret = adj.pct_change().fillna(0.0).mask(lambda x: x.abs() > 0.11, 0.0)
    clean = (1 + ret).cumprod()
    bench = ret["0050.TW"]
    retU, cleanU = ret[tickers], clean[tickers]

    mom = cleanU.shift(21) / cleanU.shift(252) - 1
    vol60 = retU.rolling(60).std()
    lo20 = cleanU.rolling(20).min().shift(1)
    q_ends = set(adj.index.to_series().groupby(adj.index.to_period("Q")).max().values)

    def run(inv_vol=False, trail_exit=False, cap=None) -> pd.Series:
        port = pd.Series(0.0, index=adj.index)
        weights: dict[str, float] = {}
        alive: dict[str, bool] = {}
        for day in adj.index:
            if weights:
                r = sum(w * retU.loc[day, t]
                        for t, w in weights.items() if alive[t])
                if trail_exit:
                    for t, w in weights.items():
                        if alive[t] and not np.isnan(lo20.loc[day, t]) \
                                and cleanU.loc[day, t] < lo20.loc[day, t]:
                            alive[t] = False
                            r -= COST * w  # 出場成本
                port.loc[day] = r
            if day in q_ends:
                snap = mom.loc[day].dropna()
                if cap is not None:
                    snap = snap[snap <= cap]
                top = list(snap.sort_values(ascending=False).head(TOP_N).index)
                if not top:
                    continue
                if inv_vol:
                    iv = 1 / vol60.loc[day, top].replace(0, np.nan)
                    iv = iv.fillna(iv.mean())
                    new_w = (iv / iv.sum()).to_dict()
                else:
                    new_w = {t: 1 / len(top) for t in top}
                changed = len(set(new_w) ^ set(weights)) / max(len(new_w), 1)
                port.loc[day] -= COST * min(changed, 2.0)
                weights = new_w
                alive = {t: True for t in weights}
        return port.loc[port.ne(0).idxmax():]

    variants = {
        "M1 等權(原版)": run(),
        "M3 反波動率加權": run(inv_vol=True),
        "M4 個股20日低出場": run(trail_exit=True),
        "M3+M4 合體": run(inv_vol=True, trail_exit=True),
        "M5 剔除>150%": run(cap=1.5),
        "M5 剔除>300%": run(cap=3.0),
    }
    print(f"{'變體':<16} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7}")
    start_idx = list(variants.values())[0].index[0]
    for name, port in variants.items():
        s = stats(port)
        print(f"{name:<16} {s['cagr']:>8.1%} {s['mdd']:>8.1%} {s['sharpe']:>7.2f}")
    b = stats(bench.loc[start_idx:])
    print(f"{'0050 B&H':<16} {b['cagr']:>8.1%} {b['mdd']:>8.1%} {b['sharpe']:>7.2f}")
