"""策略驗證:參數網格穩健性 + walk-forward 樣本外測試。

python scripts/validate_strategy.py

1. 參數網格:15 組 SMA 快慢線組合跑全樣本 — 看 edge 是普遍存在
   還是只屬於幸運參數(看中位數,不看最大值)。
2. Walk-forward:訓練 2 年選參數 → 下 1 年樣本外測試 → 滾動。
   聚合所有樣本外區段,與同期 buy-and-hold 對比。這是唯一算數的結果。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from backtest.engine import run_backtest, _sharpe, _max_drawdown, _cagr
from data.binance_feed import load
from strategy.momentum import SmaCross

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
GRID = [(f, s) for f in (10, 20, 30, 50) for s in (50, 100, 150, 200) if f < s]
TRAIN_DAYS = 730
TEST_DAYS = 365
FEE = 0.001
SLIP = 0.0005


def strat_returns(ohlcv: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    """策略日報酬序列(訊號 shift 1 根,含費用)。"""
    strategy = SmaCross(fast=fast, slow=slow)
    signal = strategy.generate_signals(ohlcv)
    position = signal.shift(1).fillna(0.0)
    daily_ret = ohlcv["close"].pct_change().fillna(0.0)
    turnover = position.diff().abs().fillna(position.iloc[0])
    return position * daily_ret - turnover * (FEE + SLIP)


def grid_search(ohlcv: pd.DataFrame, symbol: str) -> None:
    print(f"\n=== {symbol} 參數網格(全樣本 {ohlcv.index[0].date()} ~ "
          f"{ohlcv.index[-1].date()})===")
    rows = []
    for fast, slow in GRID:
        r = run_backtest(ohlcv, SmaCross(fast, slow), symbol, FEE, SLIP)
        m = r.metrics
        rows.append((f"{fast}/{slow}", m["cagr"], m["max_drawdown"],
                     m["sharpe"], r.n_trades))
    rows.sort(key=lambda x: -x[3])
    print(f"{'參數':>8} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} {'交易數':>5}")
    for name, cagr, mdd, sharpe, n in rows:
        print(f"{name:>8} {cagr:>7.1%} {mdd:>7.1%} {sharpe:>7.2f} {n:>6}")

    sharpes = [x[3] for x in rows]
    bh_ret = ohlcv["close"].pct_change().fillna(0.0)
    print(f"\nSharpe 中位數 {np.median(sharpes):.2f} | 最差 {min(sharpes):.2f} | "
          f"B&H Sharpe {_sharpe(bh_ret):.2f}")
    print(f"正 Sharpe 參數比例: {sum(s > 0 for s in sharpes)}/{len(sharpes)}")


def walk_forward(ohlcv: pd.DataFrame, symbol: str) -> None:
    print(f"\n=== {symbol} Walk-Forward(訓練 {TRAIN_DAYS}d → 測試 {TEST_DAYS}d)===")
    oos_parts = []
    print(f"{'測試區間':>24} {'選用參數':>10} {'策略':>8} {'B&H':>8}")

    start = 0
    while start + TRAIN_DAYS + TEST_DAYS <= len(ohlcv):
        train = ohlcv.iloc[start : start + TRAIN_DAYS]
        # 測試段往前多留 slow 根做均線暖機,但只取測試期的報酬
        test_begin = start + TRAIN_DAYS

        best, best_sharpe = None, -np.inf
        for fast, slow in GRID:
            s = _sharpe(strat_returns(train, fast, slow))
            if s > best_sharpe:
                best, best_sharpe = (fast, slow), s

        fast, slow = best
        warm_begin = max(0, test_begin - slow)
        segment = ohlcv.iloc[warm_begin : test_begin + TEST_DAYS]
        rets = strat_returns(segment, fast, slow).iloc[test_begin - warm_begin:]
        oos_parts.append(rets)

        bh = ohlcv["close"].iloc[test_begin : test_begin + TEST_DAYS].pct_change().fillna(0.0)
        period = (f"{ohlcv.index[test_begin].date()}~"
                  f"{ohlcv.index[test_begin + TEST_DAYS - 1].date()}")
        print(f"{period:>24} {f'{fast}/{slow}':>10} "
              f"{(1 + rets).prod() - 1:>7.1%} {(1 + bh).prod() - 1:>7.1%}")
        start += TEST_DAYS

    oos = pd.concat(oos_parts)
    oos_equity = (1 + oos).cumprod()
    bh_oos = ohlcv["close"].pct_change().fillna(0.0).loc[oos.index]
    bh_equity = (1 + bh_oos).cumprod()

    print(f"\n樣本外聚合({oos.index[0].date()} ~ {oos.index[-1].date()},"
          f"{len(oos)} 天):")
    print(f"{'':14}{'策略(OOS)':>12}{'B&H':>10}")
    print(f"{'總報酬':14}{oos_equity.iloc[-1] - 1:>11.1%}{bh_equity.iloc[-1] - 1:>9.1%}")
    print(f"{'CAGR':14}{_cagr(oos_equity):>11.1%}{_cagr(bh_equity):>9.1%}")
    print(f"{'MaxDD':14}{_max_drawdown(oos_equity):>11.1%}{_max_drawdown(bh_equity):>9.1%}")
    print(f"{'Sharpe':14}{_sharpe(oos):>11.2f}{_sharpe(bh_oos):>9.2f}")


if __name__ == "__main__":
    for symbol in SYMBOLS:
        ohlcv = load(symbol)
        grid_search(ohlcv, symbol)
        walk_forward(ohlcv, symbol)
