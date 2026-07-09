"""美股截面動量回測:python scripts/validate_us_momentum.py

台股動量模型的美股版驗證(通過才上 UI/追蹤):
  12-1 月動量 TOP10,季調倉等權,vs SPY
  Cap 鄰域:無 / 100% / 150% / 300%
  子區段:2011-2018 / 2019-2026
在地化:清洗門檻 ±60%(美股無漲跌停,財報日 ±30% 合法);
       成本 0.2% × 換手。
⚠️ 股票池為今日 S&P500 成分(生存者偏差,結果為上限)。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import io

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from scripts.validate_tw_value import stats

START = "2010-01-01"
TOP_N = 10
COST = 0.002
CLEAN_LIMIT = 0.60


def sp500_tickers() -> list[str]:
    html = requests.get(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        headers={"User-Agent": "Mozilla/5.0"}, timeout=15).text
    df = pd.read_html(io.StringIO(html))[0]
    return [t.replace(".", "-") for t in df["Symbol"].tolist()]


if __name__ == "__main__":
    tickers = sp500_tickers()
    print(f"股票池: {len(tickers)} 檔,下載中(需幾分鐘)…")
    adj = yf.download(tickers + ["SPY"], start=START, auto_adjust=True,
                      progress=False)["Close"]
    ret = adj.pct_change().fillna(0.0)
    n_bad = int((ret.abs() > CLEAN_LIMIT).values.sum())
    ret = ret.mask(ret.abs() > CLEAN_LIMIT, 0.0)
    print(f"清洗: 剔除 {n_bad} 個 ±{CLEAN_LIMIT:.0%} 以上異常單日")
    clean = (1 + ret).cumprod()

    bench = ret["SPY"]
    tickers = [t for t in tickers if t in ret.columns]
    retU, cleanU = ret[tickers], clean[tickers]
    mom = cleanU.shift(21) / cleanU.shift(252) - 1
    q_ends = set(adj.index.to_series().groupby(adj.index.to_period("Q")).max().values)

    def run(cap=None, start="2010-12-31", end=None) -> pd.Series:
        port = pd.Series(0.0, index=adj.index)
        holdings: list[str] = []
        for day in adj.index:
            if holdings:
                port.loc[day] = retU.loc[day, holdings].mean()
            if day in q_ends:
                snap = mom.loc[day].dropna()
                if cap is not None:
                    snap = snap[snap <= cap]
                new = list(snap.sort_values(ascending=False).head(TOP_N).index)
                if new and new != holdings:
                    changed = len(set(new) ^ set(holdings)) / max(len(new), 1)
                    port.loc[day] -= COST * min(changed, 2.0)
                    holdings = new
        return port.loc[start:end].loc[lambda s: s.ne(0).cummax()]

    print(f"\n{'變體':<14} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7}")
    for name, cap in [("無 cap", None), ("cap 100%", 1.0),
                      ("cap 150%", 1.5), ("cap 300%", 3.0)]:
        s = stats(run(cap))
        print(f"{name:<14} {s['cagr']:>8.1%} {s['mdd']:>8.1%} {s['sharpe']:>7.2f}")
    b = stats(bench.loc["2010-12-31":])
    print(f"{'SPY B&H':<14} {b['cagr']:>8.1%} {b['mdd']:>8.1%} {b['sharpe']:>7.2f}")

    print("\n=== 子區段(cap 150%)===")
    for s0, s1 in [("2010-12-31", "2018-12-31"), ("2019-01-01", None)]:
        p = run(1.5, start=s0, end=s1)
        bseg = bench.loc[p.index]
        sp, sb = stats(p), stats(bseg)
        print(f"{s0[:4]}~{(s1 or '2026')[:4]}: 動量 CAGR {sp['cagr']:>6.1%} "
              f"Sharpe {sp['sharpe']:.2f} | SPY CAGR {sb['cagr']:>6.1%} "
              f"Sharpe {sb['sharpe']:.2f}")
