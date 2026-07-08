"""波動率目標化驗證:python scripts/validate_voltarget.py

Donchian 55/20 訊號不變;持倉時倉位 = min(2, 目標波動/近20日年化波動)。
目標 40%(a priori),附 30%/50% 鄰域穩健性。
成本:現貨 1x 打底,超出走合約 → 資金費率僅計 max(L-1,0);
     每日調倉 turnover 全額計手續費+滑價(保守)。
判準:Sharpe 未明確勝過 1x 即否決。窗口 2018-02 起。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from backtest.engine import _cagr, _max_drawdown, _sharpe
from data.binance_feed import load
from strategy.donchian import DonchianBreakout

FEE, SLIP = 0.001, 0.0005
FUNDING_DAILY = 0.0003
CAP = 2.0
START = "2018-02-01"


def vol_target_stats(ohlcv: pd.DataFrame, target: float | None) -> dict:
    """target=None → 固定 1x 基準。"""
    close = ohlcv["close"]
    signal = DonchianBreakout(55, 20).generate_signals(ohlcv)
    ret = close.pct_change().fillna(0.0)

    if target is None:
        lev = pd.Series(1.0, index=close.index)
    else:
        realized = ret.rolling(20).std() * np.sqrt(365)
        lev = (target / realized).clip(upper=CAP).shift(1)  # 昨日波動決定今日倉位
        lev = lev.fillna(0.0)

    position = signal.shift(1).fillna(0.0) * lev
    turnover = position.diff().abs().fillna(position.iloc[0])
    funding = FUNDING_DAILY * (position - 1).clip(lower=0)
    rets = (position * ret - turnover * (FEE + SLIP) - funding).loc[START:]

    equity = (1 + rets).cumprod()
    p = position.loc[START:]
    holding = p[p > 0]
    return {
        "cagr": _cagr(equity),
        "mdd": _max_drawdown(equity),
        "sharpe": _sharpe(rets),
        "avg_lev": float(holding.mean()) if len(holding) else 0.0,
        "max_lev": float(p.max()),
    }


if __name__ == "__main__":
    for symbol in ["BTC/USDT", "ETH/USDT"]:
        ohlcv = load(symbol)
        print(f"\n=== {symbol}({START} ~ {ohlcv.index[-1].date()})===")
        print(f"{'變體':<14} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} "
              f"{'持倉均槓桿':>8} {'最大槓桿':>7}")
        for name, target in [("1x 固定(現役)", None), ("VT 30%", 0.30),
                             ("VT 40% ←主測", 0.40), ("VT 50%", 0.50)]:
            s = vol_target_stats(ohlcv, target)
            print(f"{name:<14} {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
                  f"{s['sharpe']:>7.2f} {s['avg_lev']:>8.2f} {s['max_lev']:>7.2f}")
