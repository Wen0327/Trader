"""分鐘數據累積:python scripts/intraday_collector.py

每 6 小時跑一次(launchd StartInterval,idempotent:merge 去重,多跑無害)。
Yahoo 5m 只回溯 60 天 → 首見的 ticker 回填 60d,其餘日常抓 5d,
與本地存檔重疊比對(見 data/intraday_store.py)後落地 parquet。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import yfinance as yf

from data.intraday_store import drop_live_bar, load, merge_bars, save
from data.yahoo_feed import retry_download
from monitoring.notify import alert_on_crash, send

alert_on_crash("分鐘數據累積")


def send_chunked(header: str, lines: list[str], limit: int = 1800) -> None:
    """Discord 單則上限 ~1900 字,超過會被截斷 → 分段送。"""
    buf = header
    for line in lines:
        if len(buf) + len(line) + 1 > limit:
            send(buf)
            buf = line
        else:
            buf += "\n" + line
    send(buf)


def universe() -> list[str]:
    from data.rotation import WATCHLIST
    from data.us_screen import UNIVERSE as US_UNIVERSE
    from data.value_screen import UNIVERSE as TW_UNIVERSE
    return list({**WATCHLIST, **TW_UNIVERSE, **US_UNIVERSE})


def fetch_batch(tickers: list[str], period: str) -> pd.DataFrame:
    return retry_download(lambda: yf.download(
        tickers, period=period, interval="5m", auto_adjust=True,
        progress=False, group_by="ticker"))


def extract(batch: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """從批量結果取出單檔 OHLCV;無資料回 None(下市/停牌屬正常)。"""
    if ticker not in batch.columns.get_level_values(0):
        return None
    df = (batch[ticker].rename(columns=str.lower)
          [["open", "high", "low", "close", "volume"]]
          .dropna(subset=["open"]))
    if df.empty:
        return None
    df.index = pd.to_datetime(df.index, utc=True)
    df = drop_live_bar(df)  # 盤中抓取:未收完的活棒不進庫
    return df if len(df) else None


if __name__ == "__main__":
    tickers = universe()
    fresh_tickers = [t for t in tickers if load(t) is None]
    known_tickers = [t for t in tickers if t not in set(fresh_tickers)]

    events: list[str] = []   # 需要人知道的(重刻/衝突)→ Discord + log
    stats = {"append": 0, "rescaled": 0, "healed": 0,
             "conflict": 0, "no_data": 0}

    for group, period in ((fresh_tickers, "60d"), (known_tickers, "5d")):
        if not group:
            continue
        batch = fetch_batch(group, period)
        for t in group:
            fresh = extract(batch, t)
            if fresh is None:
                stats["no_data"] += 1
                continue
            r = merge_bars(load(t), fresh)
            if r.action == "conflict":
                events.append(f"🚨 {t} 重疊區非恆定差異,已跳過累積,待人工確認")
            else:
                save(t, r.merged)
                if r.action == "rescaled":
                    events.append(
                        f"🔔 {t} 偵測到調整因子 {r.factor:.4f},本地歷史已重刻")
                elif r.action == "healed":
                    # 活棒定稿自癒屬預期行為:只進 log,不吵 Discord
                    print(f"[heal] {t} 少量暫值棒已以定稿覆蓋")
            stats[r.action] += 1

    print(f"分鐘數據累積完成:{stats}(池 {len(tickers)} 檔,"
          f"首見回填 {len(fresh_tickers)} 檔)")
    for e in events:
        print(e)  # 事件同步落 log,Discord 被截斷也能事後稽核
    if events:
        send_chunked("## 🗄 分鐘數據累積事件", events)
