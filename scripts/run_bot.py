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
import logging.handlers
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataclasses import dataclass

from data import binance_feed, yahoo_feed
from execution.binance_broker import BinanceBroker
from execution.binance_futures_broker import BinanceFuturesTestnetBroker
from execution.portfolio import STATE_PATH, Portfolio
from monitoring import equity_log
from risk.manager import RiskConfig, RiskManager, RiskViolation
from strategy.base import Strategy
from strategy.cycle_short import CycleShort
from strategy.donchian import DonchianBreakout
from strategy.regime import RegimeFilter

FUTURES_STATE_PATH = STATE_PATH.parent / "futures_state.json"
PAPER_STATE_PATH = STATE_PATH.parent / "paper_state.json"


@dataclass(frozen=True)
class SymbolConfig:
    strategy: Strategy
    signal_ticker: str | None = None  # None = 用幣安自身 K 線;否則用 Yahoo 正股代理
    mode: str = "trade"               # trade=testnet 下單 / paper=紙上撮合 / monitor=只記錄


# 每檔標的須通過各自的長歷史驗證(見 scripts/validate_*.py)才可列入。
# TSLAB 已否決:TSLA 15 年 Donchian 無 edge(1/21)。
# QQQB:Regime200 於 QQQ 25 年驗證通過(8/9)。testnet 無此交易對 →
#       紙上撮合(價格=幣安公開行情),為 --live 決策累積影子帳本。
SYMBOL_CONFIGS: dict[str, SymbolConfig] = {
    "BTC/USDT": SymbolConfig(strategy=DonchianBreakout(55, 20)),
    "ETH/USDT": SymbolConfig(strategy=DonchianBreakout(55, 20)),
    "QQQB/USDT": SymbolConfig(
        strategy=RegimeFilter(200), signal_ticker="QQQ", mode="paper"
    ),
}
PER_POSITION_PCT = 0.10   # 每個標的目標倉位 = 權益 10%(符合單筆訂單上限)
LOOP_INTERVAL = 3600      # --loop 模式下每小時檢查一次

# 週期空單軌道(合約 testnet 紙上驗證,1x 槓桿硬鎖,2026-10 窗口結束覆盤)
# 訊號用現貨長歷史計算,執行在 USDT-M 永續。
FUTURES_SHORT_CONFIGS: dict[str, dict] = {
    "BTC/USDT:USDT": {"signal_symbol": "BTC/USDT", "strategy": CycleShort()},
    "ETH/USDT:USDT": {"signal_symbol": "ETH/USDT", "strategy": CycleShort()},
}

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        # 輪替:單檔 5MB、保留 3 份,避免每小時排程把日誌養到失控
        logging.handlers.RotatingFileHandler(
            LOGS_DIR / "bot.log", maxBytes=5_000_000, backupCount=3),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("bot")


def latest_signal(cfg: SymbolConfig, symbol: str) -> float:
    """抓日線、丟掉未收盤的最後一根、回傳最新訊號。

    lookback 依策略需求:Regime200 需 200+ 根,Donchian 需 55+ 根。
    """
    today = datetime.now(timezone.utc).date()
    if cfg.signal_ticker:
        ohlcv = yahoo_feed.fetch_ohlcv(cfg.signal_ticker, lookback_days=400)
    else:
        since = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%d")
        ohlcv = binance_feed.fetch_ohlcv(symbol, timeframe="1d", since=since)
    ohlcv = ohlcv[ohlcv.index.date < today]  # 只用已收盤 K 線
    return float(cfg.strategy.generate_signals(ohlcv).iloc[-1])


def compute_equity(broker: BinanceBroker, portfolio: Portfolio) -> float:
    """策略範圍的權益 = USDT 餘額 + 策略持倉市值(不含 testnet 贈送資產)。"""
    equity = broker.get_balance("USDT")
    for symbol, pos in portfolio.positions.items():
        if pos.amount > 0:
            equity += pos.amount * broker.get_price(symbol)
    return equity


def run_once(broker: BinanceBroker, risk: RiskManager) -> None:
    portfolio = Portfolio.load()
    risk.restore(portfolio.risk_state)

    equity = compute_equity(broker, portfolio)
    risk.update_equity(equity)
    equity_log.record("spot", equity)
    log.info(f"權益={equity:.2f} USDT, kill_switch={risk.kill_switch_active}")

    for symbol, cfg in SYMBOL_CONFIGS.items():
        if cfg.mode == "paper":
            continue  # 紙上軌道由 run_paper_once 處理
        try:
            signal = latest_signal(cfg, symbol)

            if cfg.mode == "monitor":
                log.info(f"{symbol}: [監控] {cfg.strategy.name} 訊號={signal:.0f}")
                continue

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


def run_paper_once(risk: RiskManager) -> None:
    """紙上軌道:testnet 不支援的標的,自製撮合(價格=幣安公開行情)。"""
    import ccxt

    from execution.paper_broker import PaperBroker
    public = ccxt.binance()
    broker = PaperBroker(lambda s: float(public.fetch_ticker(s)["last"]))

    portfolio = Portfolio.load(PAPER_STATE_PATH)
    risk.restore(portfolio.risk_state)
    equity = broker.get_balance("USDT") + sum(
        p.amount * broker.get_price(s)
        for s, p in portfolio.positions.items() if p.amount > 0)
    risk.update_equity(equity)
    equity_log.record("paper", equity)
    log.info(f"[紙上] 權益={equity:.2f} USDT, kill_switch={risk.kill_switch_active}")

    for symbol, cfg in SYMBOL_CONFIGS.items():
        if cfg.mode != "paper":
            continue
        try:
            signal = latest_signal(cfg, symbol)
            pos = portfolio.get(symbol)
            price = broker.get_price(symbol)
            log.info(f"[紙上] {symbol}: 訊號={signal:.0f}, 持倉={pos.amount}, "
                     f"價格={price:.2f}")

            if signal > 0 and pos.amount == 0:
                target_value = equity * PER_POSITION_PCT
                amount = broker.amount_to_precision(symbol, target_value / price)
                risk.check_order(side="buy", order_value=amount * price,
                                 current_position_value=0.0, equity=equity)
                result = broker.market_order(symbol, "buy", amount)
                if result.filled > 0:  # 零成交防護
                    portfolio.set(symbol, result.filled, result.avg_price or price)
                    log.info(f"[紙上] {symbol}: 買入 {result.filled} @ "
                             f"{result.avg_price} (id={result.order_id})")

            elif signal == 0 and pos.amount > 0:
                result = broker.market_order(symbol, "sell", pos.amount)
                portfolio.clear(symbol)
                pnl_pct = ((result.avg_price or price) / pos.entry_price - 1) * 100
                log.info(f"[紙上] {symbol}: 平倉 {result.filled} @ {result.avg_price} "
                         f"損益 {pnl_pct:+.2f}% (id={result.order_id})")
            else:
                log.info(f"[紙上] {symbol}: 無需調倉")

        except RiskViolation as e:
            log.warning(f"[紙上] {symbol}: 風控攔截 — {e}")
        except Exception:
            log.exception(f"[紙上] {symbol}: 處理失敗(跳過,下次循環重試)")

    portfolio.risk_state = risk.to_dict()
    portfolio.save()


def cycle_short_signal(strategy: Strategy, signal_symbol: str) -> float:
    """週期空單訊號:需 365+ 根現貨日線,只用已收盤 K 線。"""
    since = (datetime.now(timezone.utc) - timedelta(days=430)).strftime("%Y-%m-%d")
    ohlcv = binance_feed.fetch_ohlcv(signal_symbol, timeframe="1d", since=since)
    today = datetime.now(timezone.utc).date()
    ohlcv = ohlcv[ohlcv.index.date < today]
    return float(strategy.generate_signals(ohlcv).iloc[-1])


def run_futures_once(fbroker: BinanceFuturesTestnetBroker, frisk: RiskManager) -> None:
    """合約空單軌道:與現貨多單完全獨立記帳。"""
    portfolio = Portfolio.load(FUTURES_STATE_PATH)
    frisk.restore(portfolio.risk_state)
    equity = fbroker.get_balance("USDT")
    frisk.update_equity(equity)
    equity_log.record("futures", equity)
    log.info(f"[合約] 權益={equity:.2f} USDT, kill_switch={frisk.kill_switch_active}")

    for symbol, cfg in FUTURES_SHORT_CONFIGS.items():
        try:
            signal = cycle_short_signal(cfg["strategy"], cfg["signal_symbol"])
            pos = portfolio.get(symbol)
            price = fbroker.get_price(symbol)
            log.info(f"[合約] {symbol}: 訊號={signal:.0f}, 持倉={pos.amount}, "
                     f"價格={price:.2f}")

            if signal < 0 and pos.amount == 0:
                target_value = equity * PER_POSITION_PCT
                amount = fbroker.amount_to_precision(symbol, target_value / price)
                # 開空對風控而言同樣是「開新倉」,受 kill switch 與額度限制
                frisk.check_order(side="buy", order_value=amount * price,
                                  current_position_value=0.0, equity=equity)
                result = fbroker.market_order(symbol, "sell", amount)
                portfolio.set(symbol, -result.filled, result.avg_price or price)
                log.info(f"[合約] {symbol}: 開空 {result.filled} @ {result.avg_price} "
                         f"(id={result.order_id})")

            elif signal == 0 and pos.amount < 0:
                amount = fbroker.amount_to_precision(symbol, abs(pos.amount))
                result = fbroker.market_order(symbol, "buy", amount)
                portfolio.clear(symbol)
                pnl_pct = (pos.entry_price / (result.avg_price or price) - 1) * 100
                log.info(f"[合約] {symbol}: 回補 {result.filled} @ {result.avg_price} "
                         f"損益 {pnl_pct:+.2f}% (id={result.order_id})")
            else:
                log.info(f"[合約] {symbol}: 無需調倉")

        except RiskViolation as e:
            log.warning(f"[合約] {symbol}: 風控攔截 — {e}")
        except Exception:
            log.exception(f"[合約] {symbol}: 處理失敗(跳過,下次循環重試)")

    portfolio.risk_state = frisk.to_dict()
    portfolio.save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="常駐模式,每小時檢查")
    args = parser.parse_args()

    broker = BinanceBroker(testnet=True)
    assert broker.testnet, "bot 目前只允許在 testnet 執行"
    risk = RiskManager(RiskConfig())
    fbroker = BinanceFuturesTestnetBroker()
    frisk = RiskManager(RiskConfig())
    mode_tag = {"trade": "", "paper": "[紙上]", "monitor": "[監控]"}
    desc = ", ".join(
        f"{s}:{c.strategy.name}{mode_tag[c.mode]}"
        for s, c in SYMBOL_CONFIGS.items()
    )
    fdesc = ", ".join(f"{s}:{c['strategy'].name}" for s, c in FUTURES_SHORT_CONFIGS.items())
    log.info(f"Bot 啟動 (testnet, {desc} | 合約: {fdesc})")

    prisk = RiskManager(RiskConfig())

    def tick():
        run_once(broker, risk)
        run_futures_once(fbroker, frisk)
        run_paper_once(prisk)

    if args.loop:
        while True:
            tick()
            log.info(f"休眠 {LOOP_INTERVAL}s...")
            time.sleep(LOOP_INTERVAL)
    else:
        tick()
