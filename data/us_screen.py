"""美股研究瀏覽器:精選池的動量/短線位置/財報快照。

定位:研究工具,無模型宣稱 — 美股截面動量已驗證否決
(scripts/validate_us_momentum.py:前AI時代與 SPY 平手),
故不設 ✅ 選股欄、不做前瞻追蹤。工具與台股頁同款,招牌不掛。
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from data.value_screen import fetch_metrics  # 通用,直接複用

# 精選池:各板塊龍頭 ~85 檔(靜態快照 2026-07,手動維護)
UNIVERSE = {
    # 巨頭/平台
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet",
    "AMZN": "Amazon", "META": "Meta", "NVDA": "NVIDIA", "TSLA": "Tesla",
    "NFLX": "Netflix", "ORCL": "Oracle", "IBM": "IBM",
    # 半導體
    "AVGO": "Broadcom", "AMD": "AMD", "INTC": "Intel", "QCOM": "Qualcomm",
    "TXN": "德儀", "MU": "美光", "AMAT": "應材", "LRCX": "科林",
    "KLAC": "科磊", "TSM": "台積電ADR", "ASML": "ASML", "ANET": "Arista",
    "SMCI": "美超微", "ARM": "Arm",
    # 軟體
    "CRM": "Salesforce", "ADBE": "Adobe", "NOW": "ServiceNow",
    "INTU": "Intuit", "PLTR": "Palantir", "SNOW": "Snowflake",
    "CRWD": "CrowdStrike", "PANW": "Palo Alto", "DDOG": "Datadog",
    "NET": "Cloudflare", "TEAM": "Atlassian", "WDAY": "Workday", "U": "Unity",
    # 金融
    "JPM": "摩根大通", "BAC": "美銀", "WFC": "富國", "GS": "高盛",
    "MS": "摩根士丹利", "BLK": "貝萊德", "V": "Visa", "MA": "Mastercard",
    "AXP": "美國運通", "BRK-B": "波克夏B", "SCHW": "嘉信", "C": "花旗",
    # 醫療
    "LLY": "禮來", "UNH": "聯合健康", "JNJ": "嬌生", "ABBV": "艾伯維",
    "MRK": "默克", "PFE": "輝瑞", "TMO": "賽默飛", "ISRG": "直覺手術",
    "AMGN": "安進", "ABT": "亞培",
    # 消費
    "WMT": "沃爾瑪", "COST": "好市多", "HD": "家得寶", "MCD": "麥當勞",
    "NKE": "Nike", "SBUX": "星巴克", "LOW": "勞氏", "PG": "寶僑",
    "KO": "可口可樂", "PEP": "百事", "DIS": "迪士尼", "BKNG": "Booking",
    "ABNB": "Airbnb", "UBER": "Uber",
    # 工業/能源
    "CAT": "開拓重工", "DE": "迪爾", "BA": "波音", "GE": "奇異",
    "HON": "漢威", "LMT": "洛克希德", "RTX": "雷神", "UNP": "聯合太平洋",
    "XOM": "埃克森", "CVX": "雪佛龍", "COP": "康菲",
    # 太空
    "SPCX": "SpaceX", "RKLB": "Rocket Lab", "ASTS": "AST SpaceMobile",
    "LUNR": "Intuitive Machines",
    # 能源/AI 電力
    "CEG": "Constellation", "VST": "Vistra", "GEV": "GE Vernova",
    "OKLO": "Oklo", "SMR": "NuScale", "CCJ": "Cameco",
    # 其他
    "LIN": "林德", "NEE": "新世代能源", "TMUS": "T-Mobile",
    "PYPL": "PayPal", "COIN": "Coinbase", "MSTR": "MicroStrategy",
}

# T2 二線(同板塊次強代表,預設不顯示但保留追蹤);其餘為 T1 精華
TIER2 = {
    "WFC", "C", "MS", "SCHW", "AXP",
    "PFE", "MRK", "ABT", "AMGN",
    "PEP", "LOW", "SBUX", "NKE",
    "UNP", "HON", "RTX", "DE",
    "COP", "NEE", "LIN", "TMUS",
    "IBM", "TXN", "KLAC", "DDOG", "NET", "WDAY",
}

LOOKBACK, SKIP = 252, 21
CLEAN_LIMIT = 0.60  # 美股無漲跌停,只清分割還原錯誤等級的異常


def market_snapshot() -> tuple[dict[str, float], dict[str, dict]]:
    """(全池 12-1 動量 %, 個股短線位置)— 與台股同款算法。"""
    tickers = list(UNIVERSE)
    adj = yf.download(tickers, period="2y", auto_adjust=True,
                      progress=False)["Close"]
    ret = adj.pct_change().fillna(0.0)
    clean = (1 + ret.mask(ret.abs() > CLEAN_LIMIT, 0.0)).cumprod()
    clean = clean.mask(adj.isna())  # 上市前空白不得偽造平線歷史(SPCX 教訓)
    momentum = (clean.shift(SKIP) / clean.shift(LOOKBACK) - 1).iloc[-1].dropna()

    hi20 = clean.rolling(20).max().iloc[-1]
    lo20 = clean.rolling(20).min().iloc[-1]
    ma200 = clean.rolling(200).mean().iloc[-1]
    last = clean.iloc[-1]
    tech: dict[str, dict] = {}
    for t in tickers:
        if any(pd.isna(x) for x in (last.get(t), hi20.get(t), lo20.get(t), ma200.get(t))):
            continue
        rng = float(hi20[t] - lo20[t]) or 1e-9
        pos = round(float(last[t] - lo20[t]) / rng * 100)
        above = bool(last[t] > ma200[t])
        zone = "pullback" if (pos < 40 and above) else "high" if pos > 70 else "mid"
        tech[t] = {"range_pos_20d": pos, "above_ma200": above, "zone": zone}

    return {t: round(float(m) * 100, 1) for t, m in momentum.items()}, tech


def spy_state() -> dict | None:
    """SPY regime/熱度(純顯示 — 無條件勝率宣稱,美股無已驗證模型)。"""
    try:
        spy = yf.download("SPY", period="2y", auto_adjust=True,
                          progress=False)["Close"]
        if isinstance(spy, pd.DataFrame):
            spy = spy.iloc[:, 0]
        ma200 = spy.rolling(200).mean().iloc[-1]
        return {
            "regime_on": bool(spy.iloc[-1] > ma200),
            "pct_vs_ma200": round(float(spy.iloc[-1] / ma200 - 1) * 100, 1),
            "heat_12m_pct": round(float(spy.iloc[-1] / spy.iloc[-252] - 1) * 100, 0),
        }
    except Exception:
        return None
