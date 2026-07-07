"""替代訊號驗證:python scripts/validate_alternatives.py

三個候選,全部無參數優化(參數 a priori 固定),
在與 walk-forward 相同的樣本外窗口評估:

1. SMA 集成:15 組參數各 1/15 倉位,零挑選
2. Regime 200:收盤 > SMA200 做多,否則空手(單參數,經典值)
3. Donchian 55/20:突破 55 日高進場、跌破 20 日低出場(海龜經典值)

判準:輸給 B&H 就是輸,不再翻牌。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from backtest.engine import _cagr, _max_drawdown, _sharpe
from data.binance_feed import load

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
GRID = [(f, s) for f in (10, 20, 30, 50) for s in (50, 100, 150, 200) if f < s]
OOS_START, OOS_END = "2019-09-01", "2025-08-29"  # 與 walk-forward 相同窗口
FEE, SLIP = 0.001, 0.0005


def pos_sma_ensemble(ohlcv: pd.DataFrame) -> pd.Series:
    close = ohlcv["close"]
    sigs = []
    for fast, slow in GRID:
        sig = (close.rolling(fast).mean() > close.rolling(slow).mean()).astype(float)
        sig[close.rolling(slow).mean().isna()] = 0.0
        sigs.append(sig)
    return sum(sigs) / len(sigs)


def pos_regime200(ohlcv: pd.DataFrame) -> pd.Series:
    close = ohlcv["close"]
    ma = close.rolling(200).mean()
    sig = (close > ma).astype(float)
    sig[ma.isna()] = 0.0
    return sig


def pos_donchian(ohlcv: pd.DataFrame, entry_n: int = 55, exit_n: int = 20) -> pd.Series:
    close = ohlcv["close"]
    upper = close.rolling(entry_n).max().shift(1)
    lower = close.rolling(exit_n).min().shift(1)
    raw = pd.Series(float("nan"), index=close.index)
    raw[close > upper] = 1.0
    raw[close < lower] = 0.0
    return raw.ffill().fillna(0.0)


def evaluate(name: str, position_full: pd.Series, ohlcv: pd.DataFrame) -> dict:
    """訊號用全歷史算(均線暖機),報酬只取 OOS 窗口。"""
    position = position_full.shift(1).fillna(0.0)  # 收盤訊號,次日生效
    daily_ret = ohlcv["close"].pct_change().fillna(0.0)
    turnover = position.diff().abs().fillna(position.iloc[0])
    rets = (position * daily_ret - turnover * (FEE + SLIP)).loc[OOS_START:OOS_END]
    equity = (1 + rets).cumprod()
    return {
        "name": name,
        "total": equity.iloc[-1] - 1,
        "cagr": _cagr(equity),
        "mdd": _max_drawdown(equity),
        "sharpe": _sharpe(rets),
        "exposure": float((position.loc[OOS_START:OOS_END] > 0).mean()),
    }


if __name__ == "__main__":
    for symbol in SYMBOLS:
        ohlcv = load(symbol)
        daily_ret = ohlcv["close"].pct_change().fillna(0.0).loc[OOS_START:OOS_END]
        bh_equity = (1 + daily_ret).cumprod()

        results = [
            evaluate("SMA集成(15組)", pos_sma_ensemble(ohlcv), ohlcv),
            evaluate("Regime200", pos_regime200(ohlcv), ohlcv),
            evaluate("Donchian55/20", pos_donchian(ohlcv), ohlcv),
            {
                "name": "Buy & Hold",
                "total": bh_equity.iloc[-1] - 1,
                "cagr": _cagr(bh_equity),
                "mdd": _max_drawdown(bh_equity),
                "sharpe": _sharpe(daily_ret),
                "exposure": 1.0,
            },
        ]

        print(f"\n=== {symbol} 樣本外 {OOS_START} ~ {OOS_END} ===")
        print(f"{'策略':<16}{'總報酬':>10}{'CAGR':>8}{'MaxDD':>9}{'Sharpe':>8}{'持倉率':>8}")
        for r in results:
            print(f"{r['name']:<16}{r['total']:>9.1%}{r['cagr']:>8.1%}"
                  f"{r['mdd']:>9.1%}{r['sharpe']:>8.2f}{r['exposure']:>8.1%}")
