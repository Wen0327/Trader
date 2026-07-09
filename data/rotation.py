"""輪動監控:「AI 受害者」觀察清單 + 資金輪動比值。

論點(2026-07-08):AI 集中化若逆轉,資金輪動會先反映在比值與
受害者標的的趨勢突破上。此模組只觀察、不預測 — 進場條件依然是
各標的自己的趨勢確認(站回 200MA / 突破 55 日高),絕不接刀。
執行面:這些標的幣安買不到,實作交易需開 Alpaca(未開通)。
"""

from __future__ import annotations

import pandas as pd

from data.yahoo_feed import fetch_ohlcv

# 比值:分子強於分母且比值站上 200MA = 輪動啟動
RATIO_PAIRS = [("IWM", "QQQ"), ("RSP", "SPY")]

# 受害者觀察清單(2026-07-09 修訂:軟體股改用事件研究法篩選 —
# SaaSpocalypse 窗口 2026-01-30~02-27 超額跌幅 >15% 且營收成長 >5%,
# 見對話紀錄。CRM/ADBE/HUBS 經事件歸因排除:跌幅非該事件所致)
WATCHLIST = {
    # 宏觀輪動載具
    "IWM": "小型股 Russell 2000",
    "RSP": "S&P500 等權重",
    "XBI": "生技",
    "TAN": "太陽能",
    "EEM": "新興市場",
    "EFA": "歐日已開發",
    "IGV": "軟體板塊 ETF",
    # SaaSpocalypse 錯殺候選(事件歸因 + 基本面健康)
    "ZM": "Zoom(事件-19%,已回200MA)",
    "U": "Unity(事件-37%,營收+17%)",
    "MNDY": "Monday.com(事件-36%,營收+25%)",
    "TEAM": "Atlassian(事件-36%,營收+32%)",
    "ZS": "Zscaler(事件-26%,營收+25%)",
    "WDAY": "Workday(事件-23%,營收+14%)",
}


NEAR_PCT = 3.0  # 「接近」門檻:距目標 3% 以內

# 狀態階梯(rank 越大越接近可行動)。
# 最高級採「狀態機」語意:曾突破 55 日高且尚未跌破 20 日低 = 訊號存續,
# 小幅回落不降級 — 與 Donchian 倉位邏輯一致(2026-07-09 修正快照語意缺陷)。
STATUS = {
    0: ("watching", "⚪ 觀察中"),
    1: ("near_gate1", "🟡 接近第一道門"),
    2: ("gate1_passed", "🔵 通過第一道門"),
    3: ("near_trigger", "🟠 逼近扣扳機"),
    4: ("triggered", "🟢 訊號有效中"),
}


def classify(above_ma200: bool, pct_vs_ma200: float, pct_to_55d_high: float,
             signal_active: bool) -> dict:
    if signal_active:
        rank = 4
    elif not above_ma200:
        rank = 1 if pct_vs_ma200 >= -NEAR_PCT else 0
    elif pct_to_55d_high >= -NEAR_PCT:
        rank = 3
    else:
        rank = 2
    key, label = STATUS[rank]
    return {"status": key, "status_label": label, "status_rank": rank}


TRIGGER_LOOKBACK_DAYS = 30  # 「曾突破」回看窗口(日曆日)


def _trend_status(ticker: str) -> dict | None:
    try:
        df = fetch_ohlcv(ticker, lookback_days=400)
        close = df["close"]
        ma200 = close.rolling(200).mean().iloc[-1]
        hi55 = close.rolling(55).max().iloc[-1]
        last = close.iloc[-1]
        above = bool(last > ma200)
        vs_ma = round(float(last / ma200 - 1) * 100, 1)
        to_hi = round(float(last / hi55 - 1) * 100, 1)

        # 回看:近 30 天內曾收盤突破「當日之前的 55 日高」的最後一天
        breakout_days = close > close.rolling(55).max().shift(1)
        cutoff = close.index[-1] - pd.Timedelta(days=TRIGGER_LOOKBACK_DAYS)
        recent = breakout_days[(breakout_days) & (breakout_days.index >= cutoff)]
        last_trigger = recent.index[-1] if len(recent) else None

        # 狀態機:Donchian 倉位狀態(突破後、未破20日低 = 訊號存續)
        from strategy.donchian import DonchianBreakout
        signal_active = bool(
            DonchianBreakout(55, 20).generate_signals(df).iloc[-1] == 1.0)

        return {
            "ticker": ticker,
            "price": round(float(last), 2),
            "above_ma200": above,
            "pct_vs_ma200": vs_ma,
            "pct_to_55d_high": to_hi,
            "last_trigger_date": last_trigger.strftime("%Y-%m-%d") if last_trigger is not None else None,
            "days_since_trigger": int((close.index[-1] - last_trigger).days) if last_trigger is not None else None,
            **classify(above, vs_ma, to_hi, signal_active),
        }
    except Exception:
        return None


def _ratio_status(num: str, den: str) -> dict | None:
    try:
        a = fetch_ohlcv(num, lookback_days=400)["close"]
        b = fetch_ohlcv(den, lookback_days=400)["close"]
        ratio = (a / b).dropna()
        ma200 = ratio.rolling(200).mean().iloc[-1]
        last = ratio.iloc[-1]
        return {
            "pair": f"{num}/{den}",
            "ratio": round(float(last), 4),
            "rotation_on": bool(last > ma200),
            "pct_vs_ma200": round(float(last / ma200 - 1) * 100, 1),
        }
    except Exception:
        return None


def watch() -> dict:
    items = [
        {**s, "label": WATCHLIST[t]}
        for t in WATCHLIST if (s := _trend_status(t))
    ]
    items.sort(key=lambda w: -w["status_rank"])  # 越接近可行動排越前
    return {
        "ratios": [r for p in RATIO_PAIRS if (r := _ratio_status(*p))],
        "watchlist": items,
    }
