"""台股動量 × 恐慌部署驗證:python scripts/validate_tw_panic_deploy.py

使用者假設(2026-07-10):減倉的目的是「換到更低的成本」—
預備金應在恐慌低點部署,而非等反彈確認後追回(前測的機制,已否決)。
規則(a priori):
  正常滿倉;0050 破 200MA → 降至 75% 騰出預備金;
  部署觸發 = 0050 距 52 週高跌幅 ≥ 門檻(15%/20%/25% 三檔)→ 回到 100%;
  未達門檻即站回 MA → fallback 回補;部署後維持滿倉至下一輪熊市。
對照:A 永遠滿倉、舊版(站回 MA 才回補,MA200×75%)。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf

from data.value_screen import UNIVERSE
from scripts.validate_tw_value import stats

RESERVE_EXP = 0.75
COST = 0.004

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
    dd52 = (b50 / b50.rolling(252).max() - 1).shift(1)  # 距52週高回撤(昨日)
    idx = adj.index
    q_end_set = set(idx.to_series().groupby(idx.to_period("Q")).max().tolist())

    def run(deploy_dd: float | None, recovery_reentry: bool = False) -> pd.Series:
        """deploy_dd=None 且 recovery_reentry=False → A 滿倉基準。"""
        port = pd.Series(0.0, index=idx)
        holdings: list[str] = []
        exp = 1.0
        state = "normal"  # normal / reserved / deployed
        for day in idx:
            is_below = bool(below.loc[day])
            dd = dd52.loc[day]
            target = exp
            if deploy_dd is None and not recovery_reentry:
                target = 1.0
            else:
                if state == "normal":
                    if is_below:
                        state, target = "reserved", RESERVE_EXP
                elif state == "reserved":
                    if deploy_dd is not None and not np.isnan(dd) and dd <= -deploy_dd:
                        state, target = "deployed", 1.0   # 恐慌部署
                    elif not is_below:
                        state, target = "normal", 1.0     # fallback 回補
                elif state == "deployed":
                    if not is_below:
                        state = "normal"
            if holdings:
                port.loc[day] = exp * (
                    sum(retU.loc[day, t] for t in holdings) / len(holdings))
            if target != exp:
                port.loc[day] -= COST * abs(target - exp)
                exp = target
            if day in q_end_set:
                snap = mom.loc[day].dropna()
                snap = snap[snap <= 1.5]
                new = list(snap.sort_values(ascending=False).head(10).index)
                if not new:
                    continue
                changed = len(set(new) ^ set(holdings)) / max(len(new), 1)
                port.loc[day] -= COST * min(changed, 2.0) * exp
                holdings = new
        return port.loc[port.ne(0).idxmax():]

    print(f"{'變體':<22} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7}")
    rows = [("A 永遠滿倉", None, False),
            ("舊版 站回MA才回補", None, True),
            ("D 恐慌部署 -15%", 0.15, False),
            ("D 恐慌部署 -20%", 0.20, False),
            ("D 恐慌部署 -25%", 0.25, False)]
    for label, dd_thr, recov in rows:
        s = stats(run(dd_thr, recov))
        print(f"{label:<22} {s['cagr']:>8.1%} {s['mdd']:>8.1%} {s['sharpe']:>7.2f}")
