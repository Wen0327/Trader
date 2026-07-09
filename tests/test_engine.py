"""回測引擎:前視偏差防護、費用、指標數學。"""

import numpy as np
import pandas as pd
import pytest

from backtest.engine import _cagr, _max_drawdown, _sharpe, run_backtest
from strategy.base import Strategy


class StubStrategy(Strategy):
    """回放預先給定的訊號序列。"""

    name = "stub"

    def __init__(self, signals: list[float]):
        self._signals = signals

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        return pd.Series(self._signals, index=ohlcv.index, dtype=float)


def make_ohlcv(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D", tz="UTC")
    return pd.DataFrame({"close": closes}, index=idx)


class TestNoLookahead:
    def test_signal_day_return_is_not_captured(self):
        """訊號當天的報酬不可入帳 — 持倉必須從次日開始。

        設計:第 5 天價格翻倍,訊號「剛好」只在第 5 天為 1。
        若引擎有前視偏差,策略會吃到 +100%;正確行為是吃不到
        (次日才進場,而次日報酬為 0),最終只付一次進出成本。
        """
        closes = [100.0] * 5 + [200.0] * 5
        signals = [0, 0, 0, 0, 0, 1, 0, 0, 0, 0]
        result = run_backtest(make_ohlcv(closes), StubStrategy(signals), "TEST")
        assert result.equity.iloc[-1] < 1.0  # 只付成本,沒吃到翻倍
        assert result.equity.iloc[-1] > 0.99

    def test_always_long_captures_all_returns_minus_entry_cost(self):
        closes = [100.0, 110.0, 121.0]
        signals = [1, 1, 1]
        fee, slip = 0.001, 0.0005
        result = run_backtest(make_ohlcv(closes), StubStrategy(signals), "TEST",
                              fee_rate=fee, slippage=slip)
        # 位移一天:day1 起持倉 → 吃到 day1、day2 的 +10%;進場付一次成本
        expected = (1 - (fee + slip)) * 1.10 * 1.10 / 1.10  # day1 進場當天報酬已含
        # 明確算:pos=[0,1,1], ret=[0,.1,.1] → rets=[0, .1-cost, .1]
        expected = (1 + 0.10 - (fee + slip)) * 1.10
        assert result.equity.iloc[-1] == pytest.approx(expected, rel=1e-9)


class TestCosts:
    def test_each_position_change_pays_cost(self):
        closes = [100.0] * 6  # 價格不動,報酬全來自成本
        signals = [1, 0, 1, 0, 1, 0]  # 反覆進出
        fee, slip = 0.001, 0.0005
        result = run_backtest(make_ohlcv(closes), StubStrategy(signals), "TEST",
                              fee_rate=fee, slippage=slip)
        # position = [0,1,0,1,0,1] → 5 次變動,各付一次
        assert result.n_trades == 5
        assert result.equity.iloc[-1] == pytest.approx((1 - fee - slip) ** 5, rel=1e-9)

    def test_no_trades_no_cost(self):
        result = run_backtest(make_ohlcv([100.0] * 5), StubStrategy([0] * 5), "TEST")
        assert result.n_trades == 0
        assert result.equity.iloc[-1] == pytest.approx(1.0)


class TestMetrics:
    def test_max_drawdown(self):
        equity = pd.Series([1.0, 1.5, 0.75, 1.2])
        assert _max_drawdown(equity) == pytest.approx(0.75 / 1.5 - 1)  # -50%

    def test_max_drawdown_monotonic_up_is_zero(self):
        assert _max_drawdown(pd.Series([1.0, 1.1, 1.2])) == pytest.approx(0.0)

    def test_sharpe_zero_std(self):
        assert _sharpe(pd.Series([0.0, 0.0, 0.0])) == 0.0

    def test_sharpe_positive_returns(self):
        rets = pd.Series([0.01, 0.012, 0.008, 0.011])
        assert _sharpe(rets) > 0

    def test_cagr_doubling_in_one_year(self):
        idx = pd.date_range("2024-01-01", periods=366, freq="D", tz="UTC")
        equity = pd.Series(np.linspace(1.0, 2.0, 366), index=idx)
        assert _cagr(equity) == pytest.approx(1.0, rel=0.01)  # 一年翻倍 ≈ 100%

    def test_benchmark_is_buy_and_hold(self):
        closes = [100.0, 120.0, 90.0]
        result = run_backtest(make_ohlcv(closes), StubStrategy([0, 0, 0]), "TEST")
        assert result.benchmark.iloc[-1] == pytest.approx(0.9)
