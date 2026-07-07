"""執行回測:python scripts/run_backtest.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from backtest.engine import run_backtest
from data.binance_feed import load
from strategy.momentum import SmaCross

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

if __name__ == "__main__":
    REPORTS_DIR.mkdir(exist_ok=True)
    strategy = SmaCross(fast=20, slow=60)

    for symbol in SYMBOLS:
        ohlcv = load(symbol)
        result = run_backtest(ohlcv, strategy, symbol)
        print(result.summary())
        print("-" * 44)

        fig, ax = plt.subplots(figsize=(10, 5))
        result.equity.plot(ax=ax, label=f"Strategy ({result.strategy_name})")
        result.benchmark.plot(ax=ax, label="Buy & Hold", alpha=0.7)
        ax.set_title(f"{symbol} equity curve")
        ax.set_ylabel("Equity (start = 1.0)")
        ax.legend()
        ax.grid(alpha=0.3)
        out = REPORTS_DIR / f"{symbol.replace('/', '_')}_{result.strategy_name}.png"
        fig.savefig(out, dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"淨值曲線圖: {out}\n")
