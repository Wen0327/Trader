"""恐懼貪婪指數因子驗證:python scripts/validate_fng.py

假設(a priori 固定,不做參數掃描):
  B: Donchian 55/20,但 F&G > 75(極度貪婪)時禁止新開倉
  C: Donchian 55/20,但 F&G < 25(極度恐懼)時禁止新開倉
基準 A: 純 Donchian 55/20。
窗口: 2018-02-01(F&G 數據起點)~ 最新。BTC + ETH。
判準: 變體須在 Sharpe 上明確優於基準,否則結論為「無增量價值」。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import requests

from backtest.engine import _cagr, _max_drawdown, _sharpe
from data.binance_feed import load

FEE, SLIP = 0.001, 0.0005


def fetch_fng_history() -> pd.Series:
    r = requests.get("https://api.alternative.me/fng/",
                     params={"limit": 0, "format": "json"}, timeout=15)
    r.raise_for_status()
    rows = r.json()["data"]
    s = pd.Series(
        {pd.to_datetime(int(d["timestamp"]), unit="s", utc=True): int(d["value"])
         for d in rows}
    ).sort_index()
    return s


def donchian_position_filtered(
    close: pd.Series, fng: pd.Series,
    entry_n: int = 55, exit_n: int = 20,
    block: str | None = None,  # None | "greed"(>75 禁開) | "fear"(<25 禁開)
) -> pd.Series:
    upper = close.rolling(entry_n).max().shift(1)
    lower = close.rolling(exit_n).min().shift(1)
    fng_aligned = fng.reindex(close.index.normalize()).to_numpy()

    pos = np.zeros(len(close))
    holding = 0.0
    for i in range(len(close)):
        c = close.iloc[i]
        if holding == 0 and not np.isnan(upper.iloc[i]) and c > upper.iloc[i]:
            f = fng_aligned[i]
            blocked = (
                block == "greed" and not np.isnan(f) and f > 75
            ) or (
                block == "fear" and not np.isnan(f) and f < 25
            )
            if not blocked:
                holding = 1.0
        elif holding == 1 and not np.isnan(lower.iloc[i]) and c < lower.iloc[i]:
            holding = 0.0
        pos[i] = holding
    return pd.Series(pos, index=close.index)


def evaluate(close: pd.Series, position: pd.Series, start: str) -> dict:
    pos = position.shift(1).fillna(0.0)
    ret = close.pct_change().fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.iloc[0])
    rets = (pos * ret - turnover * (FEE + SLIP)).loc[start:]
    equity = (1 + rets).cumprod()
    return {
        "cagr": _cagr(equity),
        "mdd": _max_drawdown(equity),
        "sharpe": _sharpe(rets),
        "n_entries": int((pos.diff() > 0).sum()),
    }


if __name__ == "__main__":
    fng = fetch_fng_history()
    start = "2018-02-01"
    print(f"F&G 歷史: {fng.index[0].date()} ~ {fng.index[-1].date()}({len(fng)} 天)")

    for symbol in ["BTC/USDT", "ETH/USDT"]:
        close = load(symbol)["close"]
        variants = [
            ("A 純Donchian", None),
            ("B 貪婪>75禁開", "greed"),
            ("C 恐懼<25禁開", "fear"),
        ]
        print(f"\n=== {symbol}({start} ~ {close.index[-1].date()})===")
        print(f"{'變體':<14} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} {'進場次數':>6}")
        for name, block in variants:
            pos = donchian_position_filtered(close, fng, block=block)
            s = evaluate(close, pos, start)
            print(f"{name:<14} {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
                  f"{s['sharpe']:>7.2f} {s['n_entries']:>7}")
