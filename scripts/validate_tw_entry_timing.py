"""台股動量進場時點驗證:python scripts/validate_tw_entry_timing.py

問題(使用者提出 2026-07-10):季調倉的新進股該「開季即買」
還是「等回調再買」?
規則(a priori):
  A 即買:換倉日收盤進場(= 已驗證的原版)
  B 等回調:新進股等「20日區間位置 < 40%」的第一天才進場;
           整季等不到 → 該檔該季不買(現金空置,機會成本入帳)
  兩者共同:留任股連續持有不重進;槽位等權;成本 0.4%/進出事件。
使用者押 B,既有證據(斐波/恐貪被斬)暗示 A — 對賭,數據裁判。
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
PULLBACK_POS = 40.0

if __name__ == "__main__":
    tickers = list(UNIVERSE)
    data = yf.download(tickers + ["0050.TW"], start=START, auto_adjust=False,
                       actions=True, progress=False)
    adj = data["Adj Close"]
    ret = adj.pct_change().fillna(0.0).mask(lambda x: x.abs() > 0.11, 0.0)
    clean = (1 + ret).cumprod().mask(adj.isna())
    retU, cleanU = ret[tickers], clean[tickers]
    mom = cleanU.shift(21) / cleanU.shift(252) - 1

    hi20 = cleanU.rolling(20).max()
    lo20 = cleanU.rolling(20).min()
    rng = (hi20 - lo20).replace(0, np.nan)
    range_pos = (cleanU - lo20) / rng * 100  # 0~100

    idx = adj.index
    q_end_days = idx.to_series().groupby(idx.to_period("Q")).max().tolist()
    q_end_set = set(q_end_days)

    def run(wait_pullback: bool) -> pd.Series:
        port = pd.Series(0.0, index=idx)
        active: set[str] = set()      # 已進場持有中
        pending: set[str] = set()     # 已入選但等回調(僅 B)
        for day in idx:
            # 當日組合報酬:active 貢獻報酬,pending 視為現金(0)
            n_slots = len(active) + len(pending)
            if n_slots:
                r = sum(retU.loc[day, t] for t in active) / n_slots
                port.loc[day] = r
            # pending 檢查回調觸發(進場付成本)
            if pending:
                for t in list(pending):
                    pos_val = range_pos.loc[day, t]
                    if not np.isnan(pos_val) and pos_val < PULLBACK_POS:
                        pending.discard(t)
                        active.add(t)
                        port.loc[day] -= COST / max(n_slots, 1)
            # 季末換倉
            if day in q_end_set:
                snap = mom.loc[day].dropna()
                snap = snap[snap <= MOM_CAP]
                new = set(snap.sort_values(ascending=False).head(TOP_N).index)
                if not new:
                    continue
                dropped = (active | pending) - new
                additions = new - active - pending
                # 出場成本(pending 的沒買過,無出場成本)
                exit_cost = COST * len(dropped & active) / max(len(new), 1)
                port.loc[day] -= exit_cost
                active -= dropped
                pending -= dropped
                if wait_pullback:
                    pending |= additions
                else:
                    entry_cost = COST * len(additions) / max(len(new), 1)
                    port.loc[day] -= entry_cost
                    active |= additions
        return port.loc[port.ne(0).idxmax():]

    bench = ret["0050.TW"]
    a = run(False)
    b = run(True)
    print(f"{'變體':<12} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7}")
    for name, p in [("A 開季即買", a), ("B 等回調<40%", b)]:
        s = stats(p)
        print(f"{name:<12} {s['cagr']:>8.1%} {s['mdd']:>8.1%} {s['sharpe']:>7.2f}")
    sb = stats(bench.loc[a.index[0]:])
    print(f"{'0050 B&H':<12} {sb['cagr']:>8.1%} {sb['mdd']:>8.1%} {sb['sharpe']:>7.2f}")
