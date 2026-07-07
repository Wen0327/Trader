"""儀表板唯讀 API:.venv/bin/uvicorn dashboard.api:app --port 8787

原則:只有 GET,無任何下單/寫入端點。UI 是觀測窗,不是操作台。

結構(OOD):
- BotLogParser   解析 bot.log(權益序列、交易紀錄)
- StateStore     讀 bot_state.json(持倉、風控狀態)
- ScanStore      讀 reports/ 掃描報告
- BacktestService 即時計算策略 vs B&H 淨值曲線
路由只做組裝,不含邏輯。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class BotLogParser:
    EQUITY_RE = re.compile(
        r"^(?P<ts>[\d-]+ [\d:,]+) INFO 權益=(?P<equity>[\d.]+) USDT, "
        r"kill_switch=(?P<ks>\w+)"
    )
    TRADE_RE = re.compile(
        r"^(?P<ts>[\d-]+ [\d:,]+) INFO (?P<symbol>\S+): "
        r"(?P<action>買入|平倉) (?P<amount>[\d.]+) @ (?P<price>[\d.]+)"
        r"(?: 損益 (?P<pnl>[+-][\d.]+)%)?"
    )

    def __init__(self, log_path: Path):
        self._path = log_path

    def _lines(self) -> list[str]:
        return self._path.read_text().splitlines() if self._path.exists() else []

    def equity_points(self) -> list[dict]:
        return [
            {"ts": m["ts"], "equity": float(m["equity"])}
            for line in self._lines()
            if (m := self.EQUITY_RE.match(line))
        ]

    def latest_equity(self) -> dict | None:
        for line in reversed(self._lines()):
            if m := self.EQUITY_RE.match(line):
                return {
                    "equity": float(m["equity"]),
                    "kill_switch": m["ks"] == "True",
                    "updated_at": m["ts"],
                }
        return None

    def trades(self) -> list[dict]:
        return [
            {
                "ts": m["ts"],
                "symbol": m["symbol"],
                "side": "buy" if m["action"] == "買入" else "sell",
                "amount": float(m["amount"]),
                "price": float(m["price"]),
                "pnl_pct": float(m["pnl"]) if m["pnl"] else None,
            }
            for line in self._lines()
            if (m := self.TRADE_RE.match(line))
        ]


class StateStore:
    def __init__(self, state_path: Path):
        self._path = state_path

    def read(self) -> dict:
        return json.loads(self._path.read_text()) if self._path.exists() else {}


class ScanStore:
    def __init__(self, reports_dir: Path):
        self._dir = reports_dir

    def latest(self) -> dict:
        files = sorted(self._dir.glob("bstocks_scan_*.json"))
        if not files:
            raise FileNotFoundError("尚無掃描報告")
        return json.loads(files[-1].read_text())


class BacktestService:
    """即時計算 Donchian vs B&H。策略/引擎複用主系統模組。"""

    def run(self, symbol: str) -> dict:
        from backtest.engine import run_backtest
        from data.binance_feed import load
        from strategy.donchian import DonchianBreakout

        ohlcv = load(symbol)
        r = run_backtest(ohlcv, DonchianBreakout(55, 20), symbol)
        return {
            "symbol": symbol,
            "metrics": r.metrics,
            "n_trades": r.n_trades,
            "curve": [
                {"date": d.strftime("%Y-%m-%d"),
                 "strategy": round(float(s), 4),
                 "benchmark": round(float(b), 4)}
                for d, s, b in zip(r.equity.index, r.equity, r.benchmark)
            ],
        }


log_parser = BotLogParser(ROOT / "logs" / "bot.log")
state_store = StateStore(ROOT / "storage" / "bot_state.json")
scan_store = ScanStore(ROOT / "reports")
backtest_service = BacktestService()

app = FastAPI(title="Trader Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/status")
def status():
    latest = log_parser.latest_equity() or {}
    state = state_store.read()
    return {
        "equity": latest.get("equity"),
        "kill_switch": latest.get("kill_switch"),
        "updated_at": latest.get("updated_at"),
        "positions": state.get("positions", {}),
        "risk_state": state.get("risk_state", {}),
    }


@app.get("/api/fng")
def fear_greed():
    from data.fear_greed import fetch_latest
    return fetch_latest() or {"value": None, "label": None}


@app.get("/api/equity")
def equity_history():
    return log_parser.equity_points()


@app.get("/api/trades")
def trades():
    return log_parser.trades()


@app.get("/api/scan")
def latest_scan():
    try:
        return scan_store.latest()
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/backtest")
def backtest(symbol: str = "BTC/USDT"):
    try:
        return backtest_service.run(symbol)
    except FileNotFoundError:
        raise HTTPException(404, f"無 {symbol} 歷史數據,先跑 fetch_data.py")
