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
    """解析 bot.log。現貨與合約([合約] 前綴)兩軌都認得。"""

    EQUITY_RE = re.compile(
        r"^(?P<ts>[\d-]+ [\d:,]+) INFO (?P<track>\[合約\] |\[紙上\] )?權益=(?P<equity>[\d.]+) "
        r"USDT, kill_switch=(?P<ks>\w+)"
    )
    TRADE_RE = re.compile(
        r"^(?P<ts>[\d-]+ [\d:,]+) INFO (?P<track>\[合約\] |\[紙上\] )?(?P<symbol>\S+): "
        r"(?P<action>買入|平倉|開空|回補) (?P<amount>[\d.]+) @ (?P<price>[\d.]+)"
        r"(?: 損益 (?P<pnl>[+-][\d.]+)%)?"
    )
    SIDE = {"買入": "buy", "平倉": "sell", "開空": "short", "回補": "cover"}
    TRACK = {"[合約] ": "futures", "[紙上] ": "paper"}

    def __init__(self, log_path: Path):
        self._path = log_path

    def _lines(self) -> list[str]:
        return self._path.read_text().splitlines() if self._path.exists() else []

    @classmethod
    def _track(cls, m: re.Match) -> str:
        return cls.TRACK.get(m["track"] or "", "spot")

    @staticmethod
    def _to_utc(ts: str) -> str:
        """log 時間戳為本地時間 → 統一輸出 UTC(API 全域慣例)。"""
        from datetime import datetime, timezone
        naive = datetime.strptime(ts.split(",")[0], "%Y-%m-%d %H:%M:%S")
        return naive.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def equity_points(self, track: str = "spot") -> list[dict]:
        return [
            {"ts": self._to_utc(m["ts"]), "equity": float(m["equity"])}
            for line in self._lines()
            if (m := self.EQUITY_RE.match(line)) and self._track(m) == track
        ]

    def latest_equity(self, track: str = "spot") -> dict | None:
        for line in reversed(self._lines()):
            if (m := self.EQUITY_RE.match(line)) and self._track(m) == track:
                return {
                    "equity": float(m["equity"]),
                    "kill_switch": m["ks"] == "True",
                    "updated_at": self._to_utc(m["ts"]),
                }
        return None

    def trades(self) -> list[dict]:
        return [
            {
                "ts": self._to_utc(m["ts"]),
                "track": self._track(m),
                "symbol": m["symbol"].rstrip(":"),
                "side": self.SIDE[m["action"]],
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

    def latest(self, prefix: str = "bstocks_scan") -> dict:
        files = sorted(self._dir.glob(f"{prefix}_*.json"))
        if not files:
            raise FileNotFoundError(f"尚無 {prefix} 報告")
        return json.loads(files[-1].read_text())


class RotationService:
    """輪動數據:比值歷史與單檔序列(yfinance,1 小時 TTL 快取)。"""

    TTL = 3600

    def __init__(self):
        self._cache: dict[str, tuple[float, object]] = {}

    def _cached(self, key: str, builder):
        import time
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self.TTL:
            return hit[1]
        value = builder()
        self._cache[key] = (time.time(), value)
        return value

    def ratio_histories(self) -> list[dict]:
        from data.rotation import RATIO_PAIRS
        from data.yahoo_feed import fetch_ohlcv

        def build():
            out = []
            for num, den in RATIO_PAIRS:
                a = fetch_ohlcv(num, lookback_days=730)["close"]
                b = fetch_ohlcv(den, lookback_days=730)["close"]
                ratio = (a / b).dropna()
                ma200 = ratio.rolling(200).mean()
                out.append({
                    "pair": f"{num}/{den}",
                    "rotation_on": bool(ratio.iloc[-1] > ma200.iloc[-1]),
                    "history": [
                        {"date": d.strftime("%Y-%m-%d"),
                         "ratio": round(float(r), 4),
                         "ma200": round(float(m), 4) if m == m else None}
                        for d, r, m in zip(ratio.index, ratio, ma200)
                    ],
                })
            return out
        return self._cached("ratios", build)

    def ticker_series(self, ticker: str) -> dict:
        from data.rotation import WATCHLIST
        from data.us_screen import UNIVERSE as US_UNIVERSE
        from data.value_screen import UNIVERSE
        from data.yahoo_feed import fetch_ohlcv

        allowed = {**WATCHLIST, **UNIVERSE, **US_UNIVERSE}  # 輪動 + 台股 + 美股池
        if ticker not in allowed:
            raise KeyError(ticker)

        def build():
            df = fetch_ohlcv(ticker, lookback_days=730)
            close = df["close"]
            ma200 = close.rolling(200).mean()
            hi55 = close.rolling(55).max()
            lo20 = close.rolling(20).min()
            breakout = close > hi55.shift(1)  # 突破「當日之前」的 55 日高
            return {
                "ticker": ticker,
                "label": allowed[ticker],
                "series": [
                    {"date": d.strftime("%Y-%m-%d"),
                     "open": round(float(o), 2),
                     "high": round(float(h_), 2),
                     "low": round(float(l_), 2),
                     "close": round(float(c), 2),
                     "ma200": round(float(m), 2) if m == m else None,
                     "hi55": round(float(h), 2) if h == h else None,
                     "lo20": round(float(lo), 2) if lo == lo else None,
                     "breakout": bool(b)}
                    for d, o, h_, l_, c, m, h, lo, b in zip(
                        close.index, df["open"], df["high"], df["low"], close,
                        ma200, hi55, lo20, breakout)
                ],
            }
        return self._cached(f"ticker:{ticker}", build)


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
futures_state_store = StateStore(ROOT / "storage" / "futures_state.json")
paper_state_store = StateStore(ROOT / "storage" / "paper_state.json")
scan_store = ScanStore(ROOT / "reports")
backtest_service = BacktestService()
rotation_service = RotationService()

app = FastAPI(title="Trader Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    # 唯讀原則指「無交易操作端點」;PUT 僅用於使用者偏好(精選名單)儲存
    allow_methods=["GET", "PUT"],
    allow_headers=["*"],
)


def _track_status(track: str, store: StateStore) -> dict:
    latest = log_parser.latest_equity(track) or {}
    state = store.read()
    return {
        "equity": latest.get("equity"),
        "kill_switch": latest.get("kill_switch"),
        "updated_at": latest.get("updated_at"),
        "positions": state.get("positions", {}),
        "risk_state": state.get("risk_state", {}),
    }


@app.get("/api/status")
def status():
    spot = _track_status("spot", state_store)
    spot["futures"] = _track_status("futures", futures_state_store)
    spot["paper"] = _track_status("paper", paper_state_store)

    # 台股紙上帳本:權益取自快照紀錄(週更),持倉數取自狀態檔
    from monitoring import equity_log
    tw_points = equity_log.read("paper_tw")
    tw_state = StateStore(ROOT / "storage" / "tw_paper_state.json").read()
    spot["paper_tw"] = {
        "equity": tw_points[-1]["equity"] if tw_points else None,
        "updated_at": tw_points[-1]["ts"] if tw_points else None,
        "positions_count": len(tw_state.get("positions", {})),
    }
    return spot


@app.get("/api/fng")
def fear_greed():
    from data.fear_greed import fetch_latest
    return fetch_latest() or {"value": None, "label": None}


@app.get("/api/equity")
def equity_history(track: str = "spot"):
    """權益曲線:優先讀快照(storage/equity_history.jsonl),
    無快照時退回解析 bot.log(相容舊資料)。"""
    from monitoring import equity_log
    snapshots = equity_log.read(track)
    return snapshots if snapshots else log_parser.equity_points(track)


def _paper_reset_at() -> str:
    meta = ROOT / "storage" / "paper_meta.json"
    if meta.exists():
        return json.loads(meta.read_text()).get("reset_at", "")
    return ""


@app.get("/api/trades")
def trades():
    reset_at = _paper_reset_at()
    return [t for t in log_parser.trades()
            if t["track"] != "paper" or t["ts"] >= reset_at]


@app.get("/api/scan")
def latest_scan():
    try:
        return scan_store.latest()
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/rotation")
def rotation():
    """比值歷史(即時,快取)+ 候選人狀態(取自每日掃描報告,秒開)。"""
    try:
        watchlist = scan_store.latest().get("rotation", {}).get("watchlist", [])
    except FileNotFoundError:
        watchlist = []
    return {
        "ratios": rotation_service.ratio_histories(),
        "watchlist": watchlist,
    }


@app.get("/api/rotation/ticker")
def rotation_ticker(symbol: str):
    try:
        return rotation_service.ticker_series(symbol)
    except KeyError:
        raise HTTPException(404, f"{symbol} 不在觀察清單")


@app.get("/api/chart")
def chart(symbol: str):
    """通用單檔 K 線(白名單:輪動觀察清單 + 台股價值池)。"""
    try:
        return rotation_service.ticker_series(symbol)
    except KeyError:
        raise HTTPException(404, f"{symbol} 不在白名單")


@app.get("/api/value-screen")
def value_screen():
    try:
        return scan_store.latest("value_screen")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/us-screen")
def us_screen():
    try:
        return scan_store.latest("us_screen")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


class QuoteService:
    """批量即時報價(Yahoo,~15 分鐘延遲),60 秒 TTL。"""

    TTL = 60

    def __init__(self):
        self._cache: dict[str, tuple[float, dict]] = {}

    def quotes(self, market: str) -> dict:
        import time

        import yfinance as yf
        hit = self._cache.get(market)
        if hit and time.time() - hit[0] < self.TTL:
            return hit[1]

        if market == "us":
            from data.us_screen import UNIVERSE
        else:
            from data.value_screen import UNIVERSE
        tickers = list(UNIVERSE)
        px = yf.download(tickers, period="5d", interval="1d",
                         auto_adjust=True, progress=False)["Close"]
        out = {}
        for t in tickers:
            s = px[t].dropna() if t in px.columns else None
            if s is None or len(s) < 2:
                continue
            last, prev = float(s.iloc[-1]), float(s.iloc[-2])
            out[t] = {"price": round(last, 2),
                      "today_pct": round((last / prev - 1) * 100, 2)}
        result = {"asof": __import__("datetime").datetime.utcnow()
                  .strftime("%Y-%m-%d %H:%M:%S"), "quotes": out}
        self._cache[market] = (time.time(), result)
        return result


quote_service = QuoteService()


@app.get("/api/quotes")
def quotes(market: str = "us"):
    if market not in ("us", "tw"):
        raise HTTPException(400, "market 須為 us 或 tw")
    return quote_service.quotes(market)


STARRED_PATH = ROOT / "storage" / "starred.json"


def _read_starred() -> dict:
    if STARRED_PATH.exists():
        return json.loads(STARRED_PATH.read_text())
    return {}


@app.get("/api/starred")
def get_starred(market: str = "us"):
    return {"tickers": _read_starred().get(market, [])}


@app.put("/api/starred")
def put_starred(body: dict):
    market = body.get("market")
    tickers = body.get("tickers")
    if market not in ("us", "tw") or not isinstance(tickers, list):
        raise HTTPException(400, "需要 market(us/tw)與 tickers 列表")
    # 白名單驗證:只接受池內代號
    if market == "us":
        from data.us_screen import UNIVERSE
    else:
        from data.value_screen import UNIVERSE
    tickers = [t for t in tickers if t in UNIVERSE]
    data = _read_starred()
    data[market] = sorted(set(tickers))
    STARRED_PATH.parent.mkdir(exist_ok=True)
    STARRED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return {"tickers": data[market]}


@app.get("/api/paper")
def paper_books():
    """紙上帳本彙整:US(bot 管理)+ TW(週掃描管理)。"""
    from monitoring import equity_log

    reset_at = _paper_reset_at()
    us_state = paper_state_store.read()
    us_trades = [t for t in log_parser.trades()
                 if t["track"] == "paper" and t["ts"] >= reset_at]
    us_points = equity_log.read("paper")

    tw_state = StateStore(ROOT / "storage" / "tw_paper_state.json").read()
    tw_points = equity_log.read("paper_tw")
    tw_d_state = StateStore(ROOT / "storage" / "tw_paper_d_state.json").read()
    tw_d_points = equity_log.read("paper_tw_d")
    try:
        latest_vs = scan_store.latest("value_screen")
        tw_report = latest_vs.get("paper")
        tw_d_report = latest_vs.get("paper_d")
    except FileNotFoundError:
        tw_report = tw_d_report = None

    us_stock_state = StateStore(ROOT / "storage" / "us_stock_paper_state.json").read()
    us_stock_points = equity_log.read("paper_us_stocks")
    try:
        us_stock_report = scan_store.latest("bstocks_scan").get("us_stock_paper")
    except FileNotFoundError:
        us_stock_report = None

    return {
        "us": {
            "equity": us_points[-1]["equity"] if us_points else None,
            "positions": us_state.get("positions", {}),
            "trades": us_trades[-20:],
            "equity_curve": us_points,
        },
        "us_stocks": {
            "summary": us_stock_report,  # equity/holdings/eligible_now
            "trades": us_stock_state.get("trades", [])[-20:],
            "equity_curve": us_stock_points,
        },
        "tw": {
            "summary": tw_report,  # equity/cash/return_pct/holdings
            "trades": tw_state.get("trades", [])[-20:],
            "equity_curve": tw_points,
        },
        "tw_d": {
            "summary": tw_d_report,
            "trades": tw_d_state.get("trades", [])[-20:],
            "equity_curve": tw_d_points,
        },
    }


@app.get("/api/backtest")
def backtest(symbol: str = "BTC/USDT"):
    try:
        return backtest_service.run(symbol)
    except FileNotFoundError:
        raise HTTPException(404, f"無 {symbol} 歷史數據,先跑 fetch_data.py")
