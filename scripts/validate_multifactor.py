"""七指標投票模型驗證:python scripts/validate_multifactor.py

每個指標用教科書預設參數 + 標準多空判讀,一票一權,零優化:
  EMA50>EMA200 / RSI14>50 / 收盤>布林中軌 / MACD柱>0 /
  OBV>其20日均 / F&G>50 / 一目均衡表價格在雲上(雲中=0)
變體(a priori 固定):
  多數決: 總分 > 0 做多
  強共識: 總分 >= 4 做多
窗口 2018-02 起。對照: B&H、Donchian 55/20(現役)。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from backtest.engine import _cagr, _max_drawdown, _sharpe
from data.binance_feed import load
from scripts.validate_fng import fetch_fng_history
from strategy.donchian import DonchianBreakout

FEE, SLIP = 0.001, 0.0005
START = "2018-02-01"


def votes(ohlcv: pd.DataFrame, fng: pd.Series) -> pd.DataFrame:
    close, high, low, vol = (ohlcv[c] for c in ("close", "high", "low", "volume"))
    v = pd.DataFrame(index=ohlcv.index)

    # 1. EMA50 vs EMA200
    e50, e200 = close.ewm(span=50).mean(), close.ewm(span=200).mean()
    v["ema"] = np.where(e50 > e200, 1, -1)

    # 2. RSI(14) — Wilder 平滑
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    v["rsi"] = np.where(rsi > 50, 1, -1)

    # 3. 布林中軌(SMA20)
    v["boll"] = np.where(close > close.rolling(20).mean(), 1, -1)

    # 4. MACD(12,26,9) 柱狀圖
    macd = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    hist = macd - macd.ewm(span=9).mean()
    v["macd"] = np.where(hist > 0, 1, -1)

    # 5. OBV vs 其 20 日均
    obv = (np.sign(close.diff().fillna(0)) * vol).cumsum()
    v["obv"] = np.where(obv > obv.rolling(20).mean(), 1, -1)

    # 6. F&G > 50
    f = fng.reindex(close.index.normalize()).ffill()
    v["fng"] = np.where(f.to_numpy() > 50, 1, -1)

    # 7. 一目均衡表:價格 vs 雲(先行帶,前移26)
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    cloud_top = pd.concat([senkou_a, senkou_b], axis=1).max(axis=1)
    cloud_bot = pd.concat([senkou_a, senkou_b], axis=1).min(axis=1)
    v["ichimoku"] = np.select([close > cloud_top, close < cloud_bot], [1, -1], 0)

    # 暖機期(任一指標未形成)整列作廢
    warmup = max(200, 52 + 26)
    v.iloc[:warmup] = 0
    return v


def evaluate(close: pd.Series, position: pd.Series) -> dict:
    pos = position.shift(1).fillna(0.0)
    ret = close.pct_change().fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.iloc[0])
    rets = (pos * ret - turnover * (FEE + SLIP)).loc[START:]
    equity = (1 + rets).cumprod()
    return {
        "cagr": _cagr(equity),
        "mdd": _max_drawdown(equity),
        "sharpe": _sharpe(rets),
        "exposure": float((pos.loc[START:] > 0).mean()),
        "turns": int((pos.diff().abs() > 0).sum()),
    }


if __name__ == "__main__":
    fng = fetch_fng_history()
    for symbol in ["BTC/USDT", "ETH/USDT"]:
        ohlcv = load(symbol)
        close = ohlcv["close"]
        score = votes(ohlcv, fng).sum(axis=1)

        donch = DonchianBreakout(55, 20).generate_signals(ohlcv)
        candidates = {
            "多數決(>0)": (score > 0).astype(float),
            "強共識(>=4)": (score >= 4).astype(float),
            "Donchian(現役)": donch,
            "Buy & Hold": pd.Series(1.0, index=close.index),
        }
        print(f"\n=== {symbol}({START} ~ {close.index[-1].date()})===")
        print(f"{'模型':<16} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>7} {'持倉率':>7} {'調倉次數':>6}")
        for name, pos in candidates.items():
            s = evaluate(close, pos)
            print(f"{name:<16} {s['cagr']:>8.1%} {s['mdd']:>8.1%} "
                  f"{s['sharpe']:>7.2f} {s['exposure']:>7.1%} {s['turns']:>7}")
