"""斐波那契回調位置過濾驗證:python scripts/validate_fib.py

假設(a priori 固定):
  斐波位置 = (close - 250日低) / (250日高 - 250日低),shift 1 避免前視
  B: 位置 > 0.786(貼近大級別前高)時禁止 Donchian 進場
  C: 位置 < 0.382(反彈弱勢)時禁止 Donchian 進場
基準 A: 純 Donchian 55/20。窗口 2018-02 起,BTC + ETH。
判準: 變體須明確優於基準 Sharpe,否則結論「無增量價值」。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data.binance_feed import load
from scripts.validate_fng import evaluate  # 復用:含費用、START 對齊

SWING = 250


def donchian_fib_position(
    close: pd.Series, entry_n: int = 55, exit_n: int = 20,
    block: str | None = None,  # None | "high"(>0.786禁開) | "low"(<0.382禁開)
) -> pd.Series:
    upper = close.rolling(entry_n).max().shift(1)
    lower = close.rolling(exit_n).min().shift(1)
    hi = close.rolling(SWING).max().shift(1)
    lo = close.rolling(SWING).min().shift(1)
    fib = ((close - lo) / (hi - lo)).to_numpy()

    pos = np.zeros(len(close))
    holding = 0.0
    for i in range(len(close)):
        c = close.iloc[i]
        if holding == 0 and not np.isnan(upper.iloc[i]) and c > upper.iloc[i]:
            f = fib[i]
            blocked = not np.isnan(f) and (
                (block == "high" and f > 0.786) or (block == "low" and f < 0.382)
            )
            if not blocked:
                holding = 1.0
        elif holding == 1 and not np.isnan(lower.iloc[i]) and c < lower.iloc[i]:
            holding = 0.0
        pos[i] = holding
    return pd.Series(pos, index=close.index)


if __name__ == "__main__":
    for symbol in ["BTC/USDT", "ETH/USDT"]:
        close = load(symbol)["close"]
        variants = [
            ("A 純Donchian", None),
            ("B 貼前高>78.6%禁開", "high"),
            ("C 弱勢<38.2%禁開", "low"),
        ]
        print(f"\n=== {symbol} ===")
        print(f"{'變體':<18} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} {'進場次數':>6}")
        for name, block in variants:
            pos = donchian_fib_position(close, block=block)
            s = evaluate(close, pos, "2018-02-01")
            print(f"{name:<18} {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
                  f"{s['sharpe']:>7.2f} {s['n_entries']:>7}")
