"""假警報優化 — 預註冊最終批:python scripts/validate_tw_false_alarm.py

約定(2026-07-10,使用者同意):此為 D 版假警報鏈的最後一批測試,
5 個變體一次宣告;判準 = Sharpe ≥ 1.35(D+0.05)才採用,否則蓋棺,
不再有後續變體(同一 ~4 熊市事件樣本已迭代三輪,繼續雕 = 擲骰子)。

最終裁決(2026-07-10,使用者):D 帳維持現版(MA 觸發),
不換 E3 — 讓真實熊市的前瞻數據替所有變體蒐集乾淨證據,
下一次部署事件後可用新樣本單獨檢驗 MA 觸發 vs 回撤觸發。

變體(騰預備金觸發的三種去噪手法,部署一律 52週回撤 ≤ -20%):
  E1a/E1b 確認天數:連續 5 / 10 日收在 200MA 下才騰
  E2a/E2b 緩衝帶:收盤 < 200MA × (1-2%) / (1-3%) 才騰;站回 MA fallback
  E3 深度觸發:回撤 ≤ -10% 才騰(不用 MA);回撤收復 > -5% fallback
對照:A 滿倉、D 現版(破MA即騰)。
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
DEPLOY_DD = 0.20
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
    ma200 = b50.rolling(200).mean()
    # ⚠️ shift 後 bool 序列退化為 object dtype,對其取 ~ 是位元運算
    # (~True=-2 恆真值)→ 必須 astype(bool)。曾造成假 425 次騰金的 bug。
    below = (b50 < ma200).shift(1).fillna(False).astype(bool)
    dd52 = (b50 / b50.rolling(252).max() - 1).shift(1)
    idx = adj.index
    q_end_set = set(idx.to_series().groupby(idx.to_period("Q")).max().tolist())

    # 各變體的「騰預備金」與「fallback」條件序列
    def reserve_series(variant):
        if variant == "D":
            return below, ~below
        if variant.startswith("E1"):
            n = 5 if variant == "E1a" else 10
            consec = (below.rolling(n).sum() == n)
            return consec.fillna(False).astype(bool), ~below
        if variant.startswith("E2"):
            buf = 0.02 if variant == "E2a" else 0.03
            trig = (b50 < ma200 * (1 - buf)).shift(1).fillna(False).astype(bool)
            return trig, ~below
        if variant == "E3":
            trig = (dd52 <= -0.10).fillna(False).astype(bool)
            fb = (dd52 > -0.05).fillna(False).astype(bool)
            return trig, fb
        raise ValueError(variant)

    def run(variant):
        if variant == "A":
            trig = pd.Series(False, index=idx)
            fb = pd.Series(True, index=idx)
        else:
            trig, fb = reserve_series(variant)
        port = pd.Series(0.0, index=idx)
        holdings: list[str] = []
        exp, state = 1.0, "normal"
        n_reserves = 0
        for day in idx:
            target = exp
            if state == "normal" and trig.loc[day]:
                state, target = "reserved", RESERVE_EXP
                n_reserves += 1
            elif state == "reserved":
                if not np.isnan(dd52.loc[day]) and dd52.loc[day] <= -DEPLOY_DD:
                    state, target = "deployed", 1.0
                elif fb.loc[day]:
                    state, target = "normal", 1.0
            elif state == "deployed" and fb.loc[day]:
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
        return port.loc[port.ne(0).idxmax():], n_reserves

    print(f"{'變體':<18} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} {'騰金次數':>6}")
    for label, v in [("A 滿倉", "A"), ("D 破MA即騰(現版)", "D"),
                     ("E1a 確認5日", "E1a"), ("E1b 確認10日", "E1b"),
                     ("E2a 緩衝-2%", "E2a"), ("E2b 緩衝-3%", "E2b"),
                     ("E3 回撤-10%觸發", "E3")]:
        p, n = run(v)
        s = stats(p)
        print(f"{label:<18} {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
              f"{s['sharpe']:>7.2f} {n:>7}")
    print("\n判準:Sharpe ≥ 1.35 才採用,否則此鏈蓋棺(預註冊約定)。")
