"""TSLA(特斯拉正股)Donchian 驗證:python scripts/validate_tsla.py

目的:決定 TSLAB(代幣化 TSLA)該不該留在 bot。
TSLAB 歷史太短,用 TSLA 15 年日線代測。參數 55/20 + 鄰域,
a priori 固定,零優化。美股年化用 252 交易日。
判準:Donchian 鄰域過半數勝過 B&H Sharpe 才算有 edge。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf

FEE, SLIP = 0.001, 0.0005
DAYS = 252  # 美股年化


def donchian_position(close: pd.Series, entry_n: int, exit_n: int) -> pd.Series:
    upper = close.rolling(entry_n).max().shift(1)
    lower = close.rolling(exit_n).min().shift(1)
    raw = pd.Series(float("nan"), index=close.index)
    raw[close > upper] = 1.0
    raw[close < lower] = 0.0
    return raw.ffill().fillna(0.0)


def stats(rets: pd.Series) -> dict:
    equity = (1 + rets).cumprod()
    years = len(rets) / DAYS
    return {
        "cagr": equity.iloc[-1] ** (1 / years) - 1,
        "mdd": float((equity / equity.cummax() - 1).min()),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(DAYS)) if rets.std() else 0.0,
    }


if __name__ == "__main__":
    df = yf.download("TSLA", start="2011-01-01", progress=False, auto_adjust=True)
    close = df["Close"]["TSLA"] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
    daily_ret = close.pct_change().fillna(0.0)
    bh = stats(daily_ret)
    print(f"TSLA {close.index[0].date()} ~ {close.index[-1].date()}({len(close)} 天)")
    print(f"B&H: CAGR {bh['cagr']:.1%}, MaxDD {bh['mdd']:.1%}, Sharpe {bh['sharpe']:.2f}\n")

    print(f"{'進/出':>8} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} {'持倉率':>7}")
    wins = 0
    cells = [(e, x) for e in (40, 45, 50, 55, 60, 65, 70) for x in (15, 20, 25)]
    for entry, exit_ in cells:
        pos = donchian_position(close, entry, exit_).shift(1).fillna(0.0)
        turnover = pos.diff().abs().fillna(pos.iloc[0])
        rets = pos * daily_ret - turnover * (FEE + SLIP)
        s = stats(rets)
        win = s["sharpe"] > bh["sharpe"]
        wins += win
        mark = " ✓" if win else ""
        star = " ←" if (entry, exit_) == (55, 20) else ""
        print(f"{entry}/{exit_:>3} {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
              f"{s['sharpe']:>7.2f} {float((pos > 0).mean()):>7.1%}{mark}{star}")

    print(f"\n勝過 B&H Sharpe: {wins}/{len(cells)}")
    verdict = "✅ 有 edge,TSLAB 留在 bot" if wins > len(cells) / 2 else \
              "❌ 無穩健 edge,建議把 TSLAB 移出 bot"
    print(f"判決: {verdict}")
