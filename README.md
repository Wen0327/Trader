# Trading System

自動化交易系統:幣安加密貨幣現貨(未來擴展至美股 / bStocks)。

## 架構

```
data/        數據層(幣安公開行情 API,歷史 K 線)
strategy/    策略層(訊號產生,與執行完全解耦)
backtest/    回測引擎(含手續費、滑價,避免前視偏差)
execution/   下單引擎(尚未實作 — 先接 testnet)
risk/        風控(尚未實作 — 倉位上限、最大回撤 kill switch)
scripts/     可執行腳本
storage/     歷史數據快取(gitignored)
reports/     回測報告輸出(gitignored)
```

## 快速開始

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 抓歷史數據(公開 API,不需 key)
.venv/bin/python scripts/fetch_data.py

# 跑回測
.venv/bin/python scripts/run_backtest.py
```

## 安全原則

- API key 只放 `.env`(已 gitignore),參考 `.env.example`
- 幣安 API key 只開「讀取 + 現貨交易」,**永不開提幣權限**,綁定 IP 白名單
- 實盤前必須先通過 testnet 驗證
