"""槓桿驗證:python scripts/validate_leverage.py

Donchian 55/20 訊號不變,槓桿 L ∈ {1, 1.5, 2}(章程上限 2x)。
成本模型(a priori):
- L=1: 現貨,僅手續費+滑價
- L>1: 全倉位改放 USDT-M 永續 → 資金費率 0.01%/8h(0.03%/天)
  × L × 持倉時(歷史均值假設),交易成本 × L
爆倉檢查: 日內最低價使 1 + L×跌幅 ≤ 維持保證金 5% 即歸零,逐日掃描。
窗口: 2018-02 起。同場對照 B&H。
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
FUNDING_DAILY = 0.0003   # 0.01%/8h × 3
MAINT_MARGIN = 0.05
START = "2018-02-01"


def leveraged_stats(ohlcv: pd.DataFrame, lev: float) -> dict:
    close, low = ohlcv["close"], ohlcv["low"]
    signal = DonchianBreakout(55, 20).generate_signals(ohlcv)
    pos = signal.shift(1).fillna(0.0)
    ret = close.pct_change().fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.iloc[0])

    funding = FUNDING_DAILY * lev * pos if lev > 1 else 0.0 * pos
    rets = lev * pos * ret - lev * turnover * (FEE + SLIP) - funding
    rets = rets.loc[START:]

    # 爆倉掃描:持倉日的日內最深跌幅
    intraday = (low / close.shift(1) - 1).loc[START:]
    pos_w = pos.loc[START:]
    holding_days = pos_w > 0
    worst = float(intraday[holding_days].min()) if holding_days.any() else 0.0
    liquidated = (1 + lev * intraday[holding_days] <= MAINT_MARGIN).any() \
        if holding_days.any() else False

    equity = (1 + rets).cumprod()
    return {
        "cagr": _cagr(equity),
        "mdd": _max_drawdown(equity),
        "sharpe": _sharpe(rets),
        "worst_day": worst,
        "liquidated": bool(liquidated),
    }


if __name__ == "__main__":
    for symbol in ["BTC/USDT", "ETH/USDT"]:
        ohlcv = load(symbol)
        ret = ohlcv["close"].pct_change().fillna(0.0).loc[START:]
        bh_eq = (1 + ret).cumprod()
        print(f"\n=== {symbol}({START} ~ {ohlcv.index[-1].date()})===")
        print(f"{'變體':<12} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} {'持倉日最深單日':>10} {'爆倉':>4}")
        for lev in (1.0, 1.5, 2.0):
            s = leveraged_stats(ohlcv, lev)
            print(f"Donchian {lev}x {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
                  f"{s['sharpe']:>7.2f} {s['worst_day']:>10.1%} "
                  f"{'💀是' if s['liquidated'] else '否':>4}")
        print(f"{'Buy & Hold':<12} {_cagr(bh_eq):>8.1%} {_max_drawdown(bh_eq):>8.1%} "
              f"{_sharpe(ret):>7.2f}")
