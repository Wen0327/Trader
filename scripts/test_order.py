"""Testnet 下單流程驗證:python scripts/test_order.py

流程:查餘額 → 風控審核 → 市價買入 0.001 BTC → 查成交 → 市價賣出平倉。
只能在 testnet 執行(BinanceBroker 預設 testnet=True)。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from execution.binance_broker import BinanceBroker
from risk.manager import RiskConfig, RiskManager, RiskViolation

SYMBOL = "BTC/USDT"
AMOUNT = 0.001  # 約 60 USDT

if __name__ == "__main__":
    broker = BinanceBroker(testnet=True)
    assert broker.testnet, "此腳本只能在 testnet 執行"
    risk = RiskManager(RiskConfig())

    usdt = broker.get_balance("USDT")
    btc = broker.get_balance("BTC")
    price = broker.get_price(SYMBOL)
    equity = usdt + btc * price
    print(f"下單前: USDT={usdt:.2f}, BTC={btc:.6f}, BTC價格={price:.1f}")

    order_value = AMOUNT * price
    try:
        # current_position_value 以「策略管理的持倉」計算;
        # testnet 贈送的 1 BTC 不是策略倉位,故此處為 0。
        # (實盤時會由持倉追蹤模組提供真實數值)
        risk.check_order(
            side="buy",
            order_value=order_value,
            current_position_value=0.0,
            equity=equity,
        )
        print(f"風控通過: 買入 {AMOUNT} BTC(約 {order_value:.2f} USDT)")
    except RiskViolation as e:
        sys.exit(f"風控攔截: {e}")

    buy = broker.market_order(SYMBOL, "buy", AMOUNT)
    print(f"買單: id={buy.order_id} 狀態={buy.status} "
          f"成交={buy.filled} 均價={buy.avg_price}")

    sell = broker.market_order(SYMBOL, "sell", AMOUNT)
    print(f"賣單: id={sell.order_id} 狀態={sell.status} "
          f"成交={sell.filled} 均價={sell.avg_price}")

    usdt_after = broker.get_balance("USDT")
    print(f"下單後: USDT={usdt_after:.2f}(往返成本 {usdt - usdt_after:.4f} USDT)")

    # 驗證風控會攔截超額訂單
    print("\n驗證風控攔截(嘗試下超過權益 10% 的單)...")
    try:
        risk.check_order(
            side="buy",
            order_value=equity * 0.5,
            current_position_value=0,
            equity=equity,
        )
        print("⚠️ 風控未攔截,有 bug!")
    except RiskViolation as e:
        print(f"✅ 風控正確攔截: {e}")
