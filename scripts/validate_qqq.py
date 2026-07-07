"""QQQ(納斯達克 100 ETF 正股)趨勢策略驗證:python scripts/validate_qqq.py

目的:決定 QQQB(代幣化 QQQ)可否成為 bot 的美股標的。
候選(全部 a priori 固定,零優化):
- Donchian 55/20 + 鄰域 21 組
- 200 日均線 regime(收盤 > MA200 持有)— 指數趨勢過濾的文獻經典
判準:候選需在 Sharpe 上勝過 B&H,且 Donchian 需鄰域過半數確認。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf

FEE, SLIP = 0.001, 0.0005
DAYS = 252


def donchian_position(close: pd.Series, entry_n: int, exit_n: int) -> pd.Series:
    upper = close.rolling(entry_n).max().shift(1)
    lower = close.rolling(exit_n).min().shift(1)
    raw = pd.Series(float("nan"), index=close.index)
    raw[close > upper] = 1.0
    raw[close < lower] = 0.0
    return raw.ffill().fillna(0.0)


def regime_position(close: pd.Series, n: int = 200) -> pd.Series:
    ma = close.rolling(n).mean()
    sig = (close > ma).astype(float)
    sig[ma.isna()] = 0.0
    return sig


def net_returns(close: pd.Series, position: pd.Series) -> pd.Series:
    pos = position.shift(1).fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.iloc[0])
    return pos * close.pct_change().fillna(0.0) - turnover * (FEE + SLIP)


def stats(rets: pd.Series) -> dict:
    equity = (1 + rets).cumprod()
    years = len(rets) / DAYS
    return {
        "cagr": equity.iloc[-1] ** (1 / years) - 1,
        "mdd": float((equity / equity.cummax() - 1).min()),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(DAYS)) if rets.std() else 0.0,
    }


if __name__ == "__main__":
    df = yf.download("QQQ", start="2000-01-01", progress=False, auto_adjust=True)
    close = df["Close"]["QQQ"] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
    bh = stats(close.pct_change().fillna(0.0))
    print(f"QQQ {close.index[0].date()} ~ {close.index[-1].date()}({len(close)} 天)")
    print(f"B&H: CAGR {bh['cagr']:.1%}, MaxDD {bh['mdd']:.1%}, Sharpe {bh['sharpe']:.2f}\n")

    # 200MA regime
    r = stats(net_returns(close, regime_position(close)))
    mark = "✓" if r["sharpe"] > bh["sharpe"] else "✗"
    print(f"Regime200 : CAGR {r['cagr']:.1%}, MaxDD {r['mdd']:.1%}, "
          f"Sharpe {r['sharpe']:.2f} {mark}\n")

    # Donchian 鄰域
    print(f"{'進/出':>8} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7}")
    wins = 0
    cells = [(e, x) for e in (40, 45, 50, 55, 60, 65, 70) for x in (15, 20, 25)]
    for entry, exit_ in cells:
        s = stats(net_returns(close, donchian_position(close, entry, exit_)))
        win = s["sharpe"] > bh["sharpe"]
        wins += win
        star = " ←" if (entry, exit_) == (55, 20) else ""
        print(f"{entry}/{exit_:>3} {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
              f"{s['sharpe']:>7.2f}{' ✓' if win else ''}{star}")
    print(f"\nDonchian 勝過 B&H Sharpe: {wins}/{len(cells)}")
