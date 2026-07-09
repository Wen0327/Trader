"""台股價值篩選:穩定營收 + 高殖利率 + 體質過濾。

定位:給使用者手動操作的研究工具(價值型選股池),與趨勢系統完全分離。
「產業前景」不可量化,留給人腦 — 篩選器只做可檢驗的部分。

股票池:台股大型+中型代表(靜態快照 2026-07,成分變動時需手動更新)。
數據:yfinance(.TW),與 Yahoo奇摩股市同源。
"""

from __future__ import annotations

import yfinance as yf

# 篩選門檻(a priori 預設,可調)
MIN_DIVIDEND_YIELD = 3.0   # 殖利率 %
MIN_REVENUE_GROWTH = 0.0   # 營收成長 %
MIN_PROFIT_MARGIN = 0.0    # 獲利率 %(排除虧損中的價值陷阱)

UNIVERSE = {
    # 半導體/電子
    "2330.TW": "台積電", "2454.TW": "聯發科", "2303.TW": "聯電",
    "3711.TW": "日月光投控", "3034.TW": "聯詠", "3037.TW": "欣興",
    "2379.TW": "瑞昱", "3008.TW": "大立光", "2408.TW": "南亞科",
    "6239.TW": "力成", "8046.TW": "南電", "2383.TW": "台光電",
    "2327.TW": "國巨", "6531.TW": "愛普", "3443.TW": "創意",
    "5269.TW": "祥碩", "3529.TWO": "力旺", "6415.TW": "矽力-KY",
    # 電腦/系統
    "2317.TW": "鴻海", "2382.TW": "廣達", "2357.TW": "華碩",
    "3231.TW": "緯創", "2356.TW": "英業達", "2324.TW": "仁寶",
    "4938.TW": "和碩", "6669.TW": "緯穎", "2301.TW": "光寶科",
    "2377.TW": "微星", "2345.TW": "智邦", "2308.TW": "台達電",
    "2352.TW": "佳世達", "2353.TW": "宏碁", "6176.TW": "瑞儀",
    "2368.TW": "金像電", "2313.TW": "華通",
    # 金融
    "2881.TW": "富邦金", "2882.TW": "國泰金", "2886.TW": "兆豐金",
    "2891.TW": "中信金", "2884.TW": "玉山金", "2885.TW": "元大金",
    "2892.TW": "第一金", "2880.TW": "華南金", "2887.TW": "台新金",
    "2890.TW": "永豐金", "2883.TW": "開發金", "5880.TW": "合庫金",
    "5871.TW": "中租-KY",
    # 傳產/原物料
    "1301.TW": "台塑", "1303.TW": "南亞", "1326.TW": "台化",
    "6505.TW": "台塑化", "2002.TW": "中鋼", "1101.TW": "台泥",
    "1102.TW": "亞泥", "1605.TW": "華新", "2105.TW": "正新",
    "2049.TW": "上銀", "1590.TW": "亞德客-KY", "2059.TW": "川湖",
    # 航運/航空
    "2603.TW": "長榮", "2609.TW": "陽明", "2615.TW": "萬海",
    "2618.TW": "長榮航", "2610.TW": "華航",
    # 電信/內需
    "2412.TW": "中華電", "3045.TW": "台灣大", "4904.TW": "遠傳",
    "1216.TW": "統一", "2912.TW": "統一超", "2207.TW": "和泰車",
    "9910.TW": "豐泰", "9904.TW": "寶成", "1476.TW": "儒鴻",
    "1477.TW": "聚陽", "9945.TW": "潤泰新",
    # 面板/光電
    "2409.TW": "友達", "3481.TW": "群創",
}


def fetch_metrics(ticker: str) -> dict | None:
    """yfinance 欄位單位(1.5.x 實測):
    dividendYield 已是百分比(0.97 = 0.97%);
    revenueGrowth / profitMargins 是小數(0.168 = 16.8%)。
    逐欄位明確換算,不用啟發式猜(曾造成台積電殖利率 97% 的錯誤)。"""
    try:
        info = yf.Ticker(ticker).info
        if not info or info.get("regularMarketPrice") is None:
            return None
        dy = info.get("dividendYield")
        rg = info.get("revenueGrowth")
        pm = info.get("profitMargins")
        return {
            "ticker": ticker,
            "price": info.get("regularMarketPrice"),
            "dividend_yield": round(dy, 2) if dy is not None else None,
            "revenue_growth": round(rg * 100, 1) if rg is not None else None,
            "profit_margin": round(pm * 100, 1) if pm is not None else None,
            "pe": round(info["trailingPE"], 1) if info.get("trailingPE") else None,
            "debt_to_equity": round(info["debtToEquity"], 0) if info.get("debtToEquity") else None,
        }
    except Exception:
        return None


def _passes(m: dict) -> bool:
    return (
        m.get("dividend_yield") is not None and m["dividend_yield"] >= MIN_DIVIDEND_YIELD
        and m.get("revenue_growth") is not None and m["revenue_growth"] >= MIN_REVENUE_GROWTH
        and m.get("profit_margin") is not None and m["profit_margin"] >= MIN_PROFIT_MARGIN
    )


def screen() -> dict:
    rows = []
    for ticker, name in UNIVERSE.items():
        m = fetch_metrics(ticker)
        if m is None:
            continue
        m["name"] = name
        m["passed"] = _passes(m)
        rows.append(m)
    # 通過者在前,按殖利率排;未通過者按殖利率排在後
    rows.sort(key=lambda r: (not r["passed"], -(r.get("dividend_yield") or 0)))
    return {
        "criteria": {
            "min_dividend_yield": MIN_DIVIDEND_YIELD,
            "min_revenue_growth": MIN_REVENUE_GROWTH,
            "min_profit_margin": MIN_PROFIT_MARGIN,
        },
        "universe_size": len(UNIVERSE),
        "fetched": len(rows),
        "rows": rows,
    }
