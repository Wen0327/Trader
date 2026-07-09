"""輪動宏觀 ETF 驗證:python scripts/validate_rotation_etfs.py

對 IWM/RSP/XBI/EEM/EFA 各自跑與 QQQ 相同的流程:
- Regime200 + MA 長度鄰域(125~300)vs B&H
- Donchian 55/20 單列參考(QQQ 上已證明失敗,預期同樣不行)
判準:Regime 鄰域過半數勝 B&H Sharpe 才算該標的驗證通過。
各標的歷史起點不同(IWM 2000-、RSP 2003-、XBI 2006-、EEM/EFA 2003-)。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import yfinance as yf

from scripts.validate_qqq import (donchian_position, net_returns,
                                  regime_position, stats)

ETFS = ["IWM", "RSP", "XBI", "EEM", "EFA"]
MA_GRID = (125, 150, 175, 200, 225, 250, 275, 300)

if __name__ == "__main__":
    verdicts = {}
    for ticker in ETFS:
        df = yf.download(ticker, start="2000-01-01", progress=False, auto_adjust=True)
        close = df["Close"][ticker] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
        close = close.dropna()
        bh = stats(close.pct_change().fillna(0.0))
        print(f"\n=== {ticker}({close.index[0].date()} ~ {close.index[-1].date()})===")
        print(f"B&H: CAGR {bh['cagr']:.1%}, MaxDD {bh['mdd']:.1%}, Sharpe {bh['sharpe']:.2f}")

        wins = 0
        for n in MA_GRID:
            s = stats(net_returns(close, regime_position(close, n)))
            win = s["sharpe"] > bh["sharpe"]
            wins += win
            mark = " ✓" if win else ""
            star = " ←" if n == 200 else ""
            print(f"  Regime{n}: CAGR {s['cagr']:>6.1%}, MaxDD {s['mdd']:>7.1%}, "
                  f"Sharpe {s['sharpe']:.2f}{mark}{star}")

        d = stats(net_returns(close, donchian_position(close, 55, 20)))
        print(f"  Donchian55/20(參考): CAGR {d['cagr']:>6.1%}, "
              f"Sharpe {d['sharpe']:.2f}{' ✓' if d['sharpe'] > bh['sharpe'] else ' ✗'}")

        passed = wins > len(MA_GRID) / 2
        verdicts[ticker] = (wins, passed)
        print(f"  Regime 鄰域: {wins}/{len(MA_GRID)} → "
              f"{'✅ 驗證通過' if passed else '❌ 未通過'}")

    print("\n=== 總判決 ===")
    for t, (w, p) in verdicts.items():
        print(f"  {t}: {w}/{len(MA_GRID)} {'✅' if p else '❌'}")
