"""測試幣安 Testnet 連線:python scripts/test_connection.py"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ccxt
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def masked(key: str) -> str:
    return key[:4] + "..." if key else "(未設定)"


if __name__ == "__main__":
    api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
    api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "")
    print(f"Testnet API Key: {masked(api_key)}")

    if not api_key or not api_secret:
        sys.exit("錯誤:.env 缺少 testnet 金鑰")

    ex = ccxt.binance({"apiKey": api_key, "secret": api_secret})
    ex.set_sandbox_mode(True)  # 指向 testnet.binance.vision

    balance = ex.fetch_balance()
    nonzero = {k: v for k, v in balance["total"].items() if v and v > 0}

    print("連線成功,Testnet 帳戶餘額(非零資產):")
    for asset, amount in sorted(nonzero.items()):
        print(f"  {asset:>8}: {amount}")

    ticker = ex.fetch_ticker("BTC/USDT")
    print(f"\nBTC/USDT 最新價: {ticker['last']}")
