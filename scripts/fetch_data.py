"""抓取歷史數據:python scripts/fetch_data.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.binance_feed import fetch_ohlcv, save

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME = "1d"
SINCE = "2024-07-01"  # 過去兩年

if __name__ == "__main__":
    for symbol in SYMBOLS:
        print(f"抓取 {symbol} {TIMEFRAME} K 線(自 {SINCE})...")
        df = fetch_ohlcv(symbol, timeframe=TIMEFRAME, since=SINCE)
        path = save(df, symbol, TIMEFRAME)
        print(f"  -> {len(df)} 根 K 線,已存至 {path}")
