"""新聞情緒管道:抓取 → 消毒 → VADER 評分 → 存檔。

安全邊界:標題是外部不可信文字,經 sanitize() 後只作為顯示數據
與情緒分數(數字)輸出,絕不進入任何指令/決策路徑。
評分目前只收集存檔,未經回測驗證前不參與交易。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
SEEN_PATH = STORAGE_DIR / "news_seen.json"
ARCHIVE_PATH = STORAGE_DIR / "news_archive.jsonl"

# 交易對 → yfinance 代號(SPCXB 無對應上市公司,不在此列)
SYMBOL_MAP = {
    "BTC/USDT": "BTC-USD", "ETH/USDT": "ETH-USD",
    "TSLAB/USDT": "TSLA", "NVDAB/USDT": "NVDA", "MSFTB/USDT": "MSFT",
    "METAB/USDT": "META", "AMDB/USDT": "AMD", "INTCB/USDT": "INTC",
    "PLTRB/USDT": "PLTR", "MSTRB/USDT": "MSTR", "MUB/USDT": "MU",
    "CRCLB/USDT": "CRCL", "SNDKB/USDT": "SNDK", "LITEB/USDT": "LITE",
    "QQQB/USDT": "QQQ", "EWYB/USDT": "EWY",
}

_analyzer = SentimentIntensityAnalyzer()


def sanitize(title: str) -> str:
    """消毒:只留可見字元,壓縮空白,截斷長度。"""
    title = re.sub(r"[^\x20-\x7E\u4e00-\u9fff]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:120]


def _load_seen() -> set:
    try:
        return set(json.loads(SEEN_PATH.read_text()))
    except Exception:
        return set()


def _save_seen(ids: set) -> None:
    STORAGE_DIR.mkdir(exist_ok=True)
    SEEN_PATH.write_text(json.dumps(list(ids)[-500:]))


def fetch_news(symbol: str, limit: int = 5) -> dict:
    """回傳 {headlines: [...], sentiment: float|None, ticker: str|None}。

    sentiment 為各標題 VADER compound 分數的平均,範圍 [-1, +1]。
    抓取失敗回傳空結果,不拋例外。
    """
    ticker = SYMBOL_MAP.get(symbol)
    if not ticker:
        return {"ticker": None, "headlines": [], "sentiment": None}
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return {"ticker": ticker, "headlines": [], "sentiment": None}

    headlines, scores = [], []
    for item in raw[:limit]:
        content = item.get("content", item)
        title = sanitize(content.get("title") or "")
        if len(title) < 10:
            continue
        score = _analyzer.polarity_scores(title)["compound"]
        headlines.append({"title": title, "score": round(score, 3)})
        scores.append(score)

    sentiment = round(sum(scores) / len(scores), 3) if scores else None
    return {"ticker": ticker, "headlines": headlines, "sentiment": sentiment}


def archive(symbol: str, news: dict) -> int:
    """把「沒看過的」標題連同分數寫入 JSONL 存檔,回傳新增筆數。"""
    seen = _load_seen()
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    STORAGE_DIR.mkdir(exist_ok=True)
    with ARCHIVE_PATH.open("a") as f:
        for h in news["headlines"]:
            key = f"{news['ticker']}|{h['title']}"
            if key in seen:
                continue
            f.write(json.dumps({
                "ts": now, "symbol": symbol, "ticker": news["ticker"],
                "title": h["title"], "score": h["score"],
            }, ensure_ascii=False) + "\n")
            seen.add(key)
            added += 1
    _save_seen(seen)
    return added
