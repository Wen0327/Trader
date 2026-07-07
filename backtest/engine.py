"""向量化回測引擎。

關鍵設計:
- 訊號延遲一根 K 線執行(shift(1)),避免前視偏差
- 每次倉位變動收取手續費 + 滑價
- 同時計算 buy-and-hold 作為對照組
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from strategy.base import Strategy

TRADING_DAYS_PER_YEAR = 365  # 加密貨幣全年無休


@dataclass
class BacktestResult:
    strategy_name: str
    symbol: str
    equity: pd.Series          # 策略淨值曲線(起始 = 1.0)
    benchmark: pd.Series       # buy-and-hold 淨值曲線
    positions: pd.Series       # 實際持倉序列
    n_trades: int
    metrics: dict = field(default_factory=dict)

    def summary(self) -> str:
        m = self.metrics
        lines = [
            f"策略: {self.strategy_name}  標的: {self.symbol}",
            f"區間: {self.equity.index[0].date()} ~ {self.equity.index[-1].date()}",
            f"交易次數: {self.n_trades}",
            "",
            f"{'':16}{'策略':>12}{'買入持有':>12}",
            f"{'總報酬':16}{m['total_return']:>11.1%}{m['bh_total_return']:>11.1%}",
            f"{'年化報酬':16}{m['cagr']:>11.1%}{m['bh_cagr']:>11.1%}",
            f"{'最大回撤':16}{m['max_drawdown']:>11.1%}{m['bh_max_drawdown']:>11.1%}",
            f"{'Sharpe':16}{m['sharpe']:>11.2f}{m['bh_sharpe']:>11.2f}",
            f"{'持倉時間占比':16}{m['exposure']:>11.1%}{1.0:>11.1%}",
        ]
        return "\n".join(lines)


def _max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def _sharpe(returns: pd.Series) -> float:
    if returns.std() == 0:
        return 0.0
    return float(returns.mean() / returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def _cagr(equity: pd.Series) -> float:
    n_days = (equity.index[-1] - equity.index[0]).days
    if n_days <= 0:
        return 0.0
    return float(equity.iloc[-1] ** (365 / n_days) - 1)


def run_backtest(
    ohlcv: pd.DataFrame,
    strategy: Strategy,
    symbol: str,
    fee_rate: float = 0.001,      # 幣安現貨 taker 0.1%
    slippage: float = 0.0005,     # 滑價估計 0.05%
) -> BacktestResult:
    signal = strategy.generate_signals(ohlcv)
    # 收盤產生訊號 → 下一根 K 線才持有該倉位(避免前視偏差)
    position = signal.shift(1).fillna(0.0)

    close = ohlcv["close"]
    daily_ret = close.pct_change().fillna(0.0)

    # 倉位變動時扣手續費 + 滑價
    turnover = position.diff().abs().fillna(position.iloc[0])
    cost = turnover * (fee_rate + slippage)

    strat_ret = position * daily_ret - cost
    equity = (1 + strat_ret).cumprod()
    benchmark = (1 + daily_ret).cumprod()

    n_trades = int((position.diff().abs() > 0).sum())

    metrics = {
        "total_return": float(equity.iloc[-1] - 1),
        "cagr": _cagr(equity),
        "max_drawdown": _max_drawdown(equity),
        "sharpe": _sharpe(strat_ret),
        "exposure": float((position > 0).mean()),
        "bh_total_return": float(benchmark.iloc[-1] - 1),
        "bh_cagr": _cagr(benchmark),
        "bh_max_drawdown": _max_drawdown(benchmark),
        "bh_sharpe": _sharpe(daily_ret),
    }

    return BacktestResult(
        strategy_name=strategy.name,
        symbol=symbol,
        equity=equity,
        benchmark=benchmark,
        positions=position,
        n_trades=n_trades,
        metrics=metrics,
    )
