"""做空驗證:python scripts/validate_short.py

對稱 Donchian(a priori,不另調參數):
  多: 突破55日高進,跌破20日低出(= 現役)
  空: 跌破55日低進,突破20日高回補
變體: 純做多 / 多空雙向 / 純做空(對照)。
成本: 手續費+滑價同現貨假設;未計入合約資金費率(見結論註記)。
窗口: 2018-02 起(涵蓋兩輪熊市,對做空最公平)。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from backtest.engine import _cagr, _max_drawdown, _sharpe
from data.binance_feed import load

FEE, SLIP = 0.001, 0.0005
START = "2018-02-01"


def donchian_two_sided(close: pd.Series, mode: str) -> pd.Series:
    """mode: 'long' | 'both' | 'short'。回傳持倉序列(-1/0/1)。"""
    hi55 = close.rolling(55).max().shift(1)
    lo20 = close.rolling(20).min().shift(1)
    lo55 = close.rolling(55).min().shift(1)
    hi20 = close.rolling(20).max().shift(1)

    pos = np.zeros(len(close))
    holding = 0.0
    for i in range(len(close)):
        c = close.iloc[i]
        if np.isnan(hi55.iloc[i]):
            pos[i] = holding
            continue
        if holding == 1 and c < lo20.iloc[i]:
            holding = 0.0
        elif holding == -1 and c > hi20.iloc[i]:
            holding = 0.0
        if holding == 0:
            if mode in ("long", "both") and c > hi55.iloc[i]:
                holding = 1.0
            elif mode in ("short", "both") and c < lo55.iloc[i]:
                holding = -1.0
        pos[i] = holding
    return pd.Series(pos, index=close.index)


def evaluate(close: pd.Series, position: pd.Series) -> dict:
    pos = position.shift(1).fillna(0.0)
    ret = close.pct_change().fillna(0.0)
    turnover = pos.diff().abs().fillna(abs(pos.iloc[0]))
    rets = (pos * ret - turnover * (FEE + SLIP)).loc[START:]
    equity = (1 + rets).cumprod()
    p = pos.loc[START:]
    return {
        "cagr": _cagr(equity),
        "mdd": _max_drawdown(equity),
        "sharpe": _sharpe(rets),
        "long_pct": float((p > 0).mean()),
        "short_pct": float((p < 0).mean()),
    }


if __name__ == "__main__":
    for symbol in ["BTC/USDT", "ETH/USDT"]:
        close = load(symbol)["close"]
        print(f"\n=== {symbol}({START} ~ {close.index[-1].date()})===")
        print(f"{'變體':<10} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} {'多倉率':>7} {'空倉率':>7}")
        for name, mode in [("純做多", "long"), ("多空雙向", "both"), ("純做空", "short")]:
            s = evaluate(close, donchian_two_sided(close, mode))
            print(f"{name:<10} {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
                  f"{s['sharpe']:>7.2f} {s['long_pct']:>7.1%} {s['short_pct']:>7.1%}")
