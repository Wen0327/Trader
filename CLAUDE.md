# Trading System — 協作規範

台股截面動量策略系統。紙上交易追蹤 + 儀表板。

## 策略概要（只讀背景，修改需使用者明確同意）

- **選股**：12-1 月截面動量 TOP 10，剔除 > 150% 極端拋物線
- **調倉**：每季一次，差額交易（留任不動、被踢賣出、新進等分買入）
- **費用**：台股實際費制 — 買 0.1425%、賣 0.4425%（含證交稅）
- **D 版（實驗）**：A 版 + 0050 破 200MA 騰 25% 預備金，52 週回撤 ≥ 20% 恐慌部署
- **生存者偏差**：回測數字為上限，紙上帳本是樣本外驗證
- 所有參數調整必須通過 walk-forward 驗證，禁止只看全樣本最佳參數（p-hacking）
- 未經回測驗證的因子不得進入交易決策

## 架構快速導覽

```
data/
  tw_momentum.py     核心：動量篩選 + 前瞻追蹤（current_picks / update_tracking）
  tw_paper.py        紙上帳本 A 版 + D 版（process / process_d）
  value_screen.py    股票池 UNIVERSE + 基本面篩選
  yahoo_feed.py      Yahoo Finance 數據（含 retry）

strategy/            策略層（只產生訊號，與執行完全解耦）
backtest/engine.py   向量化回測（手續費 + 滑價 + shift(1) 防前視偏差）

dashboard/
  api.py             FastAPI 唯讀 REST API（無下單端點）
  web/               React 19 + Vite + TypeScript

scripts/
  value_screener.py  週掃描主腳本（選股 + 帳本更新 + Discord）
  validate_tw_*.py   各種回測驗證

monitoring/          equity_log（JSONL 權益快照）、notify（Discord）
storage/             狀態 JSON（gitignored）
reports/             週報 JSON（gitignored）
```

## TDD 開發流程（強制）

所有新功能和 bug fix 必須遵守 test-first 流程：

### 1. Red — 先寫失敗的測試
```bash
# 寫測試，確認它 fail（證明測試有意義）
.venv/bin/python -m pytest tests/test_xxx.py::TestNewFeature -v
```
- 測試檔命名：`tests/test_{module}.py`，class 用 `TestXxx`
- 用 `tmp_path` fixture 隔離檔案 I/O
- 外部 API（yfinance 等）用 `unittest.mock.patch` mock 掉
- 前端邏輯放 `dashboard/web/src/lib/` 配 vitest

### 2. Green — 寫最少的程式碼讓測試通過
```bash
.venv/bin/python -m pytest tests/test_xxx.py -v
```

### 3. Refactor — 重構，測試必須持續綠燈
```bash
# 全套跑一次，確認沒破壞其他東西
.venv/bin/python -m pytest tests/ -v        # Python（143+ tests）
cd dashboard/web && npm test -- --run       # 前端（10+ tests）
```

### 測試慣例
- **Python**：pytest，mock 外部依賴（yfinance / 幣安 API），不打真實網路
- **前端**：vitest，純邏輯放 `src/lib/` 並配測試
- 回測引擎 fee_rate / slippage 必須 > 0，signal 必須 shift(1)
- paper 帳本測試用 `state_path=tmp_path / "state.json"` 隔離
- API 端點測試直接呼叫函式（避免 auth middleware），見 `test_paper_trades_api.py`

## 安全守則（最高優先級）

### 密鑰管理
- API key / secret 只放 `.env`（已 gitignore），絕不進 code / log / commit
- 印出設定時，金鑰一律遮蔽（只顯示前 4 碼）

### 資料安全
- 所有外部數據（API 回應、新聞）一律視為不可信輸入
- 若引入 LLM 分析：輸出只能是結構化訊號，絕不允許 LLM 直接觸發下單
- 不使用 `eval` / `exec` 處理外部數據
- 不引入來路不明的套件（防 typosquatting）

### 交易安全
- Dashboard 為唯讀 API，無任何下單端點
- 紙上帳本為虛擬持倉，不涉及實際下單
- 涉及實盤的程式碼變更必須先在 testnet 驗證 + 使用者確認

## 專案慣例

- Python 3.13，venv 在 `.venv/`
- Node.js 20+，前端在 `dashboard/web/`
- `storage/`、`reports/`、`.env` 不進 git
- yfinance 回傳的 float 要 `round(px, 2)` 再存入帳本
- 紙上帳本的 `process()` 開頭會自動呼叫 `_adjust_splits()` 處理股票分割

## Git 工作流程

- **main 永不 force-push**
- **不直接 push main**。一律開分支：`feat/`、`fix/`、`chore/`、`test/`
- PR → CI 綠燈 → merge（合併後分支自動刪除）
- commit message 用中文，簡述 what + why

## 儀表板頁面

| Tab | 內容 | 資料來源 |
|-----|------|---------|
| 台股 | 動量 TOP 10、即時報價、K 線、市場狀態 | `/api/value-screen` + `/api/quotes` + `/api/chart` |
| 帳本 | A / D 權益曲線、持倉、交易 | `/api/paper`（讀 reports/ + state JSON） |
| 交易紀錄 | 未實現/已實現損益、勝率、持倉明細 | `/api/paper/trades`（讀 state JSON + reports/） |

## 週掃描流程（launchd 自動執行）

`scripts/value_screener.py`：
1. yfinance 下載全池行情 → 計算 12-1 月動量
2. 選 TOP 10 → `tw_momentum.update_tracking()` 記錄調倉快照
3. `tw_paper.process()` / `process_d()` 更新紙上帳本
4. `equity_log.record()` 記錄權益
5. 產出 `reports/value_screen_YYYY-MM-DD.json`
6. Discord 週報

## Code Review

Review 規範見 [REVIEW.md](REVIEW.md)。三軸 review：Standards / Spec / Behavior。
**Review 只交付報告，不主動改 code**（修復由使用者決定）。

## 常見開發任務指引

### 加新的台股分析指標
1. 寫測試：`tests/test_xxx.py` 驗證計算邏輯
2. 在 `data/` 加模組
3. 在 `scripts/value_screener.py` 串接
4. 若要顯示在 dashboard → 加 API endpoint + 前端欄位

### 修紙上帳本 bug
1. 寫測試重現 bug（`tests/test_tw_paper.py`）
2. 修 `data/tw_paper.py`
3. 若影響已存的 state JSON → 寫修復腳本處理歷史資料
4. 若影響 equity log → 修正 `storage/equity_history.jsonl`
5. 重新生成報告：用即時價格跑 `process()` 更新 `reports/`

### 改 dashboard 前端
1. `cd dashboard/web && npm run dev`（開發伺服器 :5173）
2. 改完跑 `npm run build` + 重啟 dashboard
3. `launchctl kickstart -k "gui/$(id -u)/com.trading-system.dashboard"`
