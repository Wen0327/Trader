"""永豐 Shioaji 即時數據:台股即時報價(零延遲)。

歷史日線仍由 yahoo_feed.py 提供(Shioaji 無日線 API)。
本模組只負責即時快照,取代 yfinance 的 15-20 分鐘延遲報價。

憑證從環境變數讀取:SJ_API_KEY, SJ_SECRET_KEY。
"""

from __future__ import annotations

import logging

try:
    import shioaji as sj
except ImportError:
    sj = None

logger = logging.getLogger(__name__)


class ShioajiFeed:
    """永豐即時數據 feed。建構時登入,共用 session。"""

    def __init__(self, api_key: str, secret_key: str):
        if sj is None:
            raise RuntimeError("shioaji 未安裝,請執行 pip install shioaji")
        self.api = sj.Shioaji(simulation=True)
        self.api.login(api_key=api_key, secret_key=secret_key)

    def fetch_quotes(self, tickers: list[str]) -> dict[str, dict]:
        """即時報價。回傳 {ticker: {price, volume}}。

        tickers: ["2330.TW", "3529.TWO", ...] — .TW/.TWO 自動剝離。
        """
        if not tickers:
            return {}

        contracts = []
        ticker_map: dict[str, str] = {}  # code -> original ticker
        for t in tickers:
            code = t.replace(".TWO", "").replace(".TW", "")
            contract = self.api.contracts.get(code)
            if contract is not None:
                contracts.append(contract)
                ticker_map[code] = t

        if not contracts:
            return {}

        snapshots = self.api.snapshots(contracts)
        result: dict[str, dict] = {}
        for snap in snapshots:
            original = ticker_map.get(snap.code)
            if original:
                result[original] = {
                    "price": round(float(snap.close), 2),
                    "volume": int(snap.total_volume),
                }
        return result

    def logout(self) -> None:
        self.api.logout()
