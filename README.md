# Trading System

台股截面動量策略:紙上交易追蹤 + 儀表板。

## 策略邏輯

- **選股**:12-1 月截面動量 TOP 10,剔除動量 > 150% 的極端拋物線
- **調倉**:每季一次,差額交易(留任不動、踢掉賣出、新進等分買入)
- **費用**:買 0.1425%、賣 0.4425%(含 0.3% 證交稅)
- **D 版(實驗)**:A 版 + 0050 破 200MA 騰 25% 預備金,52 週回撤 ≥ 20% 恐慌部署

回測 2010–2026:CAGR 35.1% / Sharpe 1.20(vs 0050 B&H 18.3% / 0.98)。
生存者偏差對動量策略灌水最兇,以上為上限;紙上帳本為樣本外驗證。

## 架構

```
data/          數據層(台股動量篩選、Yahoo Finance 行情)
strategy/      策略層(訊號產生,與執行完全解耦)
backtest/      回測引擎(含手續費、滑價,訊號 shift(1) 避免前視偏差)
dashboard/     儀表板(FastAPI + React)
  api.py         唯讀 REST API
  web/           React + Vite 前端
scripts/       可執行腳本(週掃描、回測驗證)
monitoring/    權益快照、異常通知
storage/       狀態檔與快取(gitignored)
reports/       掃描報告(gitignored)
tests/         pytest + vitest 測試
deploy/        launchd 服務設定
```

## 儀表板

三個頁面:

- **台股**:動量模型 TOP 10 名單、即時報價、K 線圖、市場狀態與進場提示
- **帳本**:A / D 兩版紙上帳本的權益曲線、持倉、交易紀錄
- **交易紀錄**:未實現 / 已實現損益匯總、持倉明細、完整交易歷史

## 快速開始

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 台股動量回測(2010–今)
.venv/bin/python scripts/validate_tw_momentum.py

# 啟動儀表板(開發)
.venv/bin/uvicorn dashboard.api:app --host 127.0.0.1 --port 8787
cd dashboard/web && npm ci && npm run dev

# 啟動儀表板(生產,launchd 自動管理)
launchctl load ~/Library/LaunchAgents/com.trading-system.dashboard.plist
```

儀表板預設在 http://127.0.0.1:8787(API serve 前端 build)。

## 週掃描

`scripts/value_screener.py` 每週執行:

1. 下載全池台股行情,計算 12-1 月動量
2. 選出 TOP 10 + 更新紙上帳本(A 版 + D 版)
3. 產出 `reports/value_screen_YYYY-MM-DD.json`
4. 發送 Discord 週報

## 測試

```bash
.venv/bin/python -m pytest tests/ -v       # Python
cd dashboard/web && npm test               # 前端
```

## 安全原則

- `.env`、`storage/`、`reports/` 皆 gitignored
- 紙上帳本為虛擬持倉,不涉及實際下單
- 外部數據(API 回應)一律視為不可信輸入
