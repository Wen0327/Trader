"""台股高殖利率因子回測:python scripts/validate_tw_value.py

策略: 每季末以「近12月配息 ÷ 當時股價」排名,取前10等權持有一季。
成本: 每次調倉收 0.4%(台股手續費+證交稅的保守近似,全倉計)。
對手: 0050.TW 買入持有(還原權息,含息總報酬)。
已知偏差(結論打折用):
- 生存者偏差:股票池為今日大中型股,結果為上限
- 營收/獲利過濾器無歷史數據,未納入 — 只測殖利率排序因子
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf

from data.value_screen import UNIVERSE

START = "2010-01-01"
TOP_N = 10
REBALANCE_COST = 0.004
DAYS = 252


def stats(rets: pd.Series) -> dict:
    equity = (1 + rets).cumprod()
    years = len(rets) / DAYS
    return {
        "cagr": equity.iloc[-1] ** (1 / years) - 1,
        "mdd": float((equity / equity.cummax() - 1).min()),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(DAYS)) if rets.std() else 0.0,
    }


if __name__ == "__main__":
    tickers = list(UNIVERSE)
    data = yf.download(tickers + ["0050.TW"], start=START, auto_adjust=False,
                       actions=True, progress=False)
    close = data["Close"]
    adj = data["Adj Close"]
    div = data["Dividends"].fillna(0.0)

    # 時點殖利率:近 365 日配息合計 ÷ 當日收盤
    ttm_div = div.rolling(252, min_periods=200).sum()
    yield_ = (ttm_div / close) * 100

    ret = adj.pct_change().fillna(0.0)  # 還原權息 = 含息報酬
    # 數據清洗:台股漲跌停 ±10%,單日還原報酬超過 ±11% 必為
    # Yahoo 還原係數錯誤(實測 0050 曾出現假 -75%),一律歸零
    bad = ret.abs() > 0.11
    n_bad = int(bad.values.sum())
    ret = ret.mask(bad, 0.0)
    print(f"清洗:剔除 {n_bad} 個超出漲跌停的異常單日報酬")
    bench = ret["0050.TW"].copy()
    ret = ret[tickers]
    yield_ = yield_[tickers]

    # 季末調倉日
    q_ends = close.index.to_series().groupby(close.index.to_period("Q")).max()

    port_ret = pd.Series(0.0, index=close.index)
    holdings: list[str] = []
    n_rebal = 0
    for i, day in enumerate(close.index):
        if holdings:
            port_ret.loc[day] = ret.loc[day, holdings].mean()
        if day in set(q_ends.values):
            snap = yield_.loc[day].dropna()
            snap = snap[snap > 0]
            new = list(snap.sort_values(ascending=False).head(TOP_N).index)
            if new and new != holdings:
                port_ret.loc[day] -= REBALANCE_COST
                holdings = new
                n_rebal += 1

    port_ret = port_ret.loc[port_ret.ne(0).idxmax():]  # 首次建倉起算
    bench = bench.loc[port_ret.index]

    s, b = stats(port_ret), stats(bench)
    print(f"回測 {port_ret.index[0].date()} ~ {port_ret.index[-1].date()},"
          f"調倉 {n_rebal} 次,每次持有 {TOP_N} 檔")
    print(f"{'':14}{'高殖利率TOP10':>12}{'0050 B&H':>12}")
    print(f"{'CAGR':14}{s['cagr']:>11.1%}{b['cagr']:>11.1%}")
    print(f"{'MaxDD':14}{s['mdd']:>11.1%}{b['mdd']:>11.1%}")
    print(f"{'Sharpe':14}{s['sharpe']:>11.2f}{b['sharpe']:>11.2f}")
    print("\n⚠️ 生存者偏差:股票池為今日存活的大中型股,以上為因子表現上限。")
