"""Paper trading bot 主循環(testnet)。

用法:
  python scripts/run_bot.py            # 執行一次(適合 cron / launchd 排程)
  python scripts/run_bot.py --loop     # 常駐,每小時檢查一次

流程(每個標的):
  抓最新日線(公開 API)→ 只用已收盤 K 線算訊號 → 與目前持倉比對
  → 需要調倉時經風控審核 → testnet 下單 → 更新持倉狀態 → 寫日誌
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.binance_feed import fetch_ohlcv
from execution.binance_broker import BinanceBroker
from execution.portfolio import Portfolio
from risk.manager import RiskConfig, RiskManager, RiskViolation
from strategy.momentum import SmaCross

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
PER_POSITION_PCT = 0.10   # 每個標的目標倉位 = 權益 10%(符合單筆訂單上限)
LOOP_INTERVAL = 3600      # --loop 模式下每小時檢查一次

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "bot.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("bot")


def latest_signal(strategy: SmaCross, symbol: str) -> float:
    """抓最近 ~120 天日線,丟掉未收盤的最後一根,回傳最新訊號。"""
    since = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%d")
    ohlcv = fetch_ohlcv(symbol, timeframe="1d", since=since)
    today = datetime.now(timezone.utc).date()
    ohlcv = ohlcv[ohlcv.index.date < today]  # 只用已收盤 K 線
    return float(strategy.generate_signals(ohlcv).iloc[-1])


def compute_equity(broker: BinanceBroker, portfolio: Portfolio) -> float:
    """策略範圍的權益 = USDT 餘額 + 策略持倉市值(不含 testnet 贈送資產)。"""
    equity = broker.get_balance("USDT")
    for symbol, pos in portfolio.positions.items():
        if pos.amount > 0:
            equity += pos.amount * broker.get_price(symbol)
    return equity


def run_once(broker: BinanceBroker, risk: RiskManager, strategy: SmaCross) -> None:
    portfolio = Portfolio.load()
    risk.restore(portfolio.risk_state)

    equity = compute_equity(broker, portfolio)
    risk.update_equity(equity)
    log.info(f"權益={equity:.2f} USDT, kill_switch={risk.kill_switch_active}")

    for symbol in SYMBOLS:
        try:
            signal = latest_signal(strategy, symbol)
            pos = portfolio.get(symbol)
            price = broker.get_price(symbol)
            log.info(f"{symbol}: 訊號={signal:.0f}, 持倉={pos.amount}, 價格={price:.2f}")

            if signal > 0 and pos.amount == 0:
                # 開倉:買入權益 10% 的部位
                target_value = equity * PER_POSITION_PCT
                amount = broker.amount_to_precision(symbol, target_value / price)
                risk.check_order(
                    side="buy",
                    order_value=amount * price,
                    current_position_value=0.0,
                    equity=equity,
                )
                result = broker.market_order(symbol, "buy", amount)
                portfolio.set(symbol, result.filled, result.avg_price or price)
                log.info(f"{symbol}: 買入 {result.filled} @ {result.avg_price} "
                         f"(id={result.order_id})")

            elif signal == 0 and pos.amount > 0:
                # 平倉(賣出減倉不受 kill switch 限制)
                amount = broker.amount_to_precision(symbol, pos.amount)
                result = broker.market_order(symbol, "sell", amount)
                portfolio.clear(symbol)
                pnl_pct = ((result.avg_price or price) / pos.entry_price - 1) * 100
                log.info(f"{symbol}: 平倉 {result.filled} @ {result.avg_price} "
                         f"損益 {pnl_pct:+.2f}% (id={result.order_id})")
            else:
                log.info(f"{symbol}: 無需調倉")

        except RiskViolation as e:
            log.warning(f"{symbol}: 風控攔截 — {e}")
        except Exception:
            log.exception(f"{symbol}: 處理失敗(跳過,下次循環重試)")

    portfolio.risk_state = risk.to_dict()
    portfolio.save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="常駐模式,每小時檢查")
    args = parser.parse_args()

    broker = BinanceBroker(testnet=True)
    assert broker.testnet, "bot 目前只允許在 testnet 執行"
    risk = RiskManager(RiskConfig())
    strategy = SmaCross(fast=20, slow=60)
    log.info(f"Bot 啟動 (testnet, 策略={strategy.name}, 標的={SYMBOLS})")

    if args.loop:
        while True:
            run_once(broker, risk, strategy)
            log.info(f"休眠 {LOOP_INTERVAL}s...")
            time.sleep(LOOP_INTERVAL)
    else:
        run_once(broker, risk, strategy)
