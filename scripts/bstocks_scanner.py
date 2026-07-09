"""bStocks 掃描器:python scripts/bstocks_scanner.py

掃描幣安上所有 bStocks(代幣化美股)的 24h 表現,依漲幅排名,
輸出 JSON 報告 + 一行摘要。只用幣安公開行情 API,不需要 key。

篩選條件(參考 premarket gapper 概念,調整為 bStocks 場景):
- |24h 漲跌幅| > MIN_ABS_CHANGE_PCT(漲跌都值得關注)
- 24h 成交額 > MIN_QUOTE_VOLUME USDT(排除無量標的)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ccxt

# 已知的 bStocks 交易對(BTech Holdings 發行的代幣化美股/ETF)
BSTOCKS = [
    "NVDAB/USDT", "TSLAB/USDT", "MSFTB/USDT", "METAB/USDT",
    "AMDB/USDT", "INTCB/USDT", "PLTRB/USDT", "MSTRB/USDT",
    "MUB/USDT", "CRCLB/USDT", "SNDKB/USDT", "SPCXB/USDT",
    "LITEB/USDT", "QQQB/USDT", "EWYB/USDT",
]

MIN_ABS_CHANGE_PCT = 2.0       # 24h 漲跌幅絕對值門檻
MIN_QUOTE_VOLUME = 50_000      # 24h 最低成交額(USDT)
TOP_N = 10

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def scan() -> dict:
    ex = ccxt.binance()  # 正式環境公開行情
    markets = ex.load_markets()
    available = [s for s in BSTOCKS if s in markets and markets[s]["active"]]
    tickers = ex.fetch_tickers(available)

    rows = []
    for symbol, t in tickers.items():
        change_pct = t.get("percentage")
        quote_vol = t.get("quoteVolume")
        if change_pct is None or quote_vol is None:
            continue
        rows.append({
            "symbol": symbol,
            "price": t.get("last"),
            "change_pct": round(float(change_pct), 2),
            "quote_volume_usdt": round(float(quote_vol)),
        })

    movers = [
        r for r in rows
        if abs(r["change_pct"]) > MIN_ABS_CHANGE_PCT
        and r["quote_volume_usdt"] > MIN_QUOTE_VOLUME
    ]
    movers.sort(key=lambda r: abs(r["change_pct"]), reverse=True)
    movers = movers[:TOP_N]
    for i, r in enumerate(movers, 1):
        r["rank"] = i

    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "universe_size": len(available),
        "filters": {
            "min_abs_change_pct": MIN_ABS_CHANGE_PCT,
            "min_quote_volume_usdt": MIN_QUOTE_VOLUME,
        },
        "movers": movers,
        "all": sorted(rows, key=lambda r: abs(r["change_pct"]), reverse=True),
    }


def enrich_with_news(report: dict) -> int:
    """movers + BTC/ETH 附上新聞情緒;全部標題存檔累積。回傳新增存檔筆數。"""
    from data.news_feed import archive, fetch_news

    added = 0
    for m in report["movers"]:
        news = fetch_news(m["symbol"])
        m["sentiment"] = news["sentiment"]
        m["headlines"] = [h["title"] for h in news["headlines"][:2]]
        added += archive(m["symbol"], news)

    report["crypto_sentiment"] = {}
    for sym in ["BTC/USDT", "ETH/USDT"]:
        news = fetch_news(sym)
        report["crypto_sentiment"][sym] = news["sentiment"]
        added += archive(sym, news)

    from data.fear_greed import fetch_latest
    report["fear_greed"] = fetch_latest()

    from data.rotation import watch
    report["rotation"] = watch()
    return added


if __name__ == "__main__":
    report = scan()
    archived = enrich_with_news(report)

    REPORTS_DIR.mkdir(exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = REPORTS_DIR / f"bstocks_scan_{date_str}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    movers = report["movers"]
    if movers:
        top = ", ".join(
            f"{m['symbol'].split('/')[0]} ({m['change_pct']:+.1f}%"
            + (f", 情緒 {m['sentiment']:+.2f}" if m.get("sentiment") is not None else "")
            + ")"
            for m in movers[:3]
        )
        print(f"bStocks Movers: {len(movers)} 檔符合條件。Top: {top}")
        for m in movers[:3]:
            for h in m.get("headlines", []):
                print(f"    {m['symbol'].split('/')[0]}: {h}")
    else:
        print(f"bStocks Movers: 今日無標的符合條件"
              f"(|漲跌|>{MIN_ABS_CHANGE_PCT}%, 量>{MIN_QUOTE_VOLUME:,} USDT)")
    cs = report.get("crypto_sentiment", {})
    print(f"Crypto 情緒: " + ", ".join(
        f"{k.split('/')[0]} {v:+.2f}" if v is not None else f"{k.split('/')[0]} n/a"
        for k, v in cs.items()))
    print(f"新聞存檔: +{archived} 筆")

    rot = report.get("rotation", {})
    for r in rot.get("ratios", []):
        print(f"輪動比值 {r['pair']}: {r['ratio']} "
              f"({'🟢啟動' if r['rotation_on'] else '⚪未啟動'}, "
              f"vs 200MA {r['pct_vs_ma200']:+.1f}%)")
    ready = [w for w in rot.get("watchlist", []) if w["above_ma200"]]
    if ready:
        print("觀察清單站上 200MA: " + ", ".join(
            f"{w['ticker']}(距55日高 {w['pct_to_55d_high']:+.1f}%)" for w in ready))
    print(f"完整報告: {out}")
