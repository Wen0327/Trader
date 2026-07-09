"""台股截面動量回測:python scripts/validate_tw_momentum.py

假設(使用者提出,2026-07-10):0050 的弱點是市值加權
(肥豬躺平照樣重倉)+ 成分汰換遲滯(題材股納入晚)。
截面動量直接對治:只持有 12-1 月動量前 10 的股票。

變體(a priori):
  M1: 12-1 動量 TOP10,季調倉,等權
  M2: M1 + 僅限 200MA 之上(不足額時持有現金)
成本: 0.4% × 實際換手比例。數據清洗:單日 ±11% 以上視為錯誤。
⚠️ 生存者偏差對動量策略灌水最兇(存活者=當年贏家),結果為上限。
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
COST = 0.004  # 換手成本(單邊近似,乘以換手比例)


if __name__ == "__main__":
    tickers = list(UNIVERSE)
    data = yf.download(tickers + ["0050.TW"], start=START, auto_adjust=False,
                       actions=True, progress=False)
    adj = data["Adj Close"]
    ret = adj.pct_change().fillna(0.0)
    ret = ret.mask(ret.abs() > 0.11, 0.0)  # 台股漲跌停清洗
    clean = (1 + ret).cumprod()  # 用乾淨報酬重建價格路徑

    bench = ret["0050.TW"]
    ret = ret[tickers]
    clean = clean[tickers]

    # 12-1 動量:252 日報酬,跳過最近 21 日
    momentum = clean.shift(21) / clean.shift(252) - 1
    ma200 = clean.rolling(200).mean()

    q_ends = set(adj.index.to_series().groupby(adj.index.to_period("Q")).max().values)

    def run(require_ma: bool) -> pd.Series:
        port = pd.Series(0.0, index=adj.index)
        holdings: list[str] = []
        for day in adj.index:
            if holdings:
                port.loc[day] = ret.loc[day, holdings].mean()
            if day in q_ends:
                snap = momentum.loc[day].dropna()
                if require_ma:
                    above = clean.loc[day] > ma200.loc[day]
                    snap = snap[above.reindex(snap.index).fillna(False)]
                new = list(snap.sort_values(ascending=False).head(TOP_N).index)
                if new and new != holdings:
                    changed = len(set(new) ^ set(holdings)) / max(len(new), 1)
                    port.loc[day] -= COST * min(changed, 2.0)
                    holdings = new
        return port.loc[port.ne(0).idxmax():]

    results = {
        "M1 動量TOP10": run(False),
        "M2 動量+200MA": run(True),
        "0050 B&H": None,
    }
    print(f"{'變體':<14} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7}")
    start_idx = None
    for name, port in results.items():
        if port is None:
            port = bench.loc[start_idx:]
        else:
            start_idx = start_idx or port.index[0]
        s = stats(port)
        print(f"{name:<14} {s['cagr']:>8.1%} {s['mdd']:>8.1%} {s['sharpe']:>7.2f}")
    print("\n⚠️ 生存者偏差:動量策略被此偏差灌水最兇,以上為上限。")
