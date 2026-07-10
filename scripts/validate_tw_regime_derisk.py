"""台股動量 × 熊市減碼驗證:python scripts/validate_tw_regime_derisk.py

問題(使用者提出 2026-07-10):0050 跌破 200MA 時把動量組合降曝險
(留現金給熊市),全清 vs 分批哪個好?會更好嗎?
結論(2010-2026):
  不減碼   CAGR 32.7%  MDD -37.7%  Sharpe 1.26  ← 維持
  降至75%       30.4%      -34.6%        1.27(雜訊級改善,口味選擇)
  全清倉        23.0%      -41.9%        1.11(最差 — 回撤反而更深)
機制:台股熊市為急跌+V反彈,全清者固定錯過右半邊;
     動量季調倉自帶換血防禦,外掛擇時只是干擾。
決策:A 版維持滿倉。相關否決:回調進場(validate_tw_entry_timing)、
     BTC週期錨(不適用台股,未測)。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf

from data.value_screen import UNIVERSE
from scripts.validate_tw_value import stats

if __name__ == "__main__":
    tickers = list(UNIVERSE)
    data = yf.download(tickers + ["0050.TW"], start="2010-01-01",
                       auto_adjust=False, actions=True, progress=False)
    adj = data["Adj Close"]
    ret = adj.pct_change().fillna(0.0).mask(lambda x: x.abs() > 0.11, 0.0)
    clean = (1 + ret).cumprod().mask(adj.isna())
    retU, cleanU = ret[tickers], clean[tickers]
    mom = cleanU.shift(21) / cleanU.shift(252) - 1
    b50 = clean["0050.TW"]
    below = (b50 < b50.rolling(200).mean()).shift(1).fillna(False)
    idx = adj.index
    q_end_set = set(idx.to_series().groupby(idx.to_period("Q")).max().tolist())

    def run(bear_exposure: float) -> pd.Series:
        port = pd.Series(0.0, index=idx)
        holdings: list[str] = []
        exp = 1.0
        for day in idx:
            target = bear_exposure if below.loc[day] else 1.0
            if holdings:
                port.loc[day] = exp * (
                    sum(retU.loc[day, t] for t in holdings) / len(holdings))
            if target != exp:
                port.loc[day] -= 0.004 * abs(target - exp)
                exp = target
            if day in q_end_set:
                snap = mom.loc[day].dropna()
                snap = snap[snap <= 1.5]
                new = list(snap.sort_values(ascending=False).head(10).index)
                if not new:
                    continue
                changed = len(set(new) ^ set(holdings)) / max(len(new), 1)
                port.loc[day] -= 0.004 * min(changed, 2.0) * exp
                holdings = new
        return port.loc[port.ne(0).idxmax():]

    print(f"{'熊市曝險':<12} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7}")
    for e in (1.0, 0.75, 0.5, 0.25, 0.0):
        s = stats(run(e))
        label = "A 不減碼" if e == 1.0 else f"降至 {e * 100:.0f}%"
        print(f"{label:<12} {s['cagr']:>8.1%} {s['mdd']:>8.1%} {s['sharpe']:>7.2f}")
