# Trading System

台股截面動量策略：紙上交易追蹤 + 儀表板。

## 策略邏輯

### 核心假設

0050 的弱點是市值加權（大牛股躺平照樣重倉）+ 成分汰換遲滯（題材股納入晚）。
截面動量直接對治：只持有近期漲最多的股票，每季汰弱留強。

### 選股規則

1. **股票池**：台股大型 + 中型代表約 80 檔（`data/value_screen.py` 中的 `UNIVERSE`）
2. **動量指標**：12-1 月截面動量 = 近 252 個交易日報酬，跳過最近 21 日（避短期反轉雜訊）
3. **極端剔除**：動量 > 150% 的拋物線股不選（防動量崩潰，回撤 -40.6% → -37.7%）
4. **選出**：動量最高的 TOP 10 檔

### 買賣規則

| 事件 | 動作 |
|------|------|
| 每季末 | 重新排名，產出新 TOP 10 名單 |
| 留任（仍在 TOP 10）| 不動，省手續費 |
| 被踢出名單 | 全部賣出 |
| 新進名單 | 用賣出釋放的現金等分買入 |

- 差額交易制，不是全賣全買
- 台股實際費制：買 0.1425%（券商手續費）、賣 0.4425%（手續費 + 0.3% 證交稅）
- 整股交易（不買零股）

### D 版（恐慌部署實驗）

在 A 版基礎上加一個狀態機，試圖在熊市低點加碼：

| 狀態 | 觸發條件 | 動作 |
|------|---------|------|
| normal → reserved | 0050 跌破 200MA | 賣出各持倉 25%，存入預備金 |
| reserved → deployed | 0050 從 52 週高點回撤 ≥ 20% | 預備金全數按比例加碼現有持倉 |
| reserved → normal | 0050 站回 200MA（未達 -20%）| 預備金回補，回歸正常 |
| deployed → normal | 0050 站回 200MA | 回歸正常 |

回測 Sharpe 1.30 vs A 版 1.26，但歷史僅 ~4 次熊市事件，需更多樣本外驗證。

### 回測結果（2010–2026）

| 變體 | CAGR | MaxDD | Sharpe |
|------|------|-------|--------|
| M1 動量 TOP10 | 35.1% | -40.6% | 1.20 |
| M2 動量 + 200MA 濾網 | 37.6% | -41.3% | 1.30 |
| 0050 B&H | 18.3% | -33.8% | 0.98 |

> ⚠️ **生存者偏差**：免費數據只含現存股票，歷年下市的輸家被排除。動量策略受此偏差灌水最兇（存活者 = 當年贏家），以上數字為上限。紙上帳本的意義在於累積真實樣本外證據。

## 架構

```
data/            數據層
  tw_momentum.py   台股動量篩選 + 前瞻追蹤
  tw_paper.py      紙上帳本（A 標準版 + D 恐慌部署版）
  value_screen.py  股票池 + 基本面篩選
  yahoo_feed.py    Yahoo Finance 數據擷取（含重試）

strategy/        策略層（訊號產生，與執行完全解耦）
backtest/        回測引擎（含手續費、滑價，訊號 shift(1) 避免前視偏差）

dashboard/       儀表板
  api.py           FastAPI 唯讀 REST API（無下單端點）
  auth.py          Magic link 登入 + session cookie
  web/             React 19 + Vite + TypeScript 前端

scripts/         可執行腳本
  value_screener.py  週掃描（動量選股 + 紙上帳本更新 + Discord 週報）
  validate_tw_*.py   回測驗證腳本（動量、進場時機、恐慌部署等）

monitoring/      權益快照（JSONL）、異常通知（Discord）
deploy/          launchd plist（macOS 服務自動啟動）
tests/           pytest + vitest
storage/         狀態檔與快取（gitignored）
reports/         掃描報告（gitignored）
```

## 儀表板

| 頁面 | 內容 |
|------|------|
| **台股** | 動量 TOP 10 名單（✅ 標記）、即時報價（60 秒更新）、K 線圖（日/分鐘多時框）、市場狀態（0050 vs 200MA、熱度分桶、進場提示） |
| **帳本** | A / D 兩版紙上帳本：權益曲線、持倉明細（含金額損益）、近期交易 |
| **交易紀錄** | 未實現 / 已實現損益匯總、勝率、平均獲利虧損、持倉表、完整交易歷史 |

Dashboard 有登入認證（magic link email），只有白名單內的 email 可存取。

## 環境需求

- Python 3.13+
- Node.js 20+（前端開發/build）
- macOS（deploy 用 launchd；Linux 可改用 systemd）

## 快速開始

```bash
# 1. clone
git clone <repo-url>
cd Trader

# 2. Python 環境
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. 環境變數
cp .env.example .env
# 編輯 .env：填入 DISCORD_WEBHOOK（選填）、ALLOWED_EMAILS 等

# 4. 前端 build
cd dashboard/web
npm ci
npm run build
cd ../..

# 5. 台股動量回測（驗證環境正常）
.venv/bin/python scripts/validate_tw_momentum.py

# 6. 啟動儀表板
.venv/bin/uvicorn dashboard.api:app --host 127.0.0.1 --port 8787
# 開瀏覽器 http://127.0.0.1:8787
```

### 生產部署（macOS launchd）

```bash
# deploy/*.plist 裡的 __PROJECT_DIR__ 佔位符要先替換成實際路徑
sed -i '' "s|__PROJECT_DIR__|$(pwd)|g" deploy/*.plist

# 安裝 dashboard 服務（開機自啟、crash 自動重啟）
cp deploy/com.trading-system.dashboard.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.trading-system.dashboard.plist

# 重啟
launchctl kickstart -k "gui/$(id -u)/com.trading-system.dashboard"
```

## 週掃描流程

`scripts/value_screener.py` 由 launchd 每週自動執行：

1. 下載全池台股行情（yfinance）
2. 計算 12-1 月截面動量，選出 TOP 10
3. 更新紙上帳本（A + D 版差額換倉）
4. 記錄權益快照（`storage/equity_history.jsonl`）
5. 產出報告（`reports/value_screen_YYYY-MM-DD.json`）
6. 發送 Discord 週報

## 回測驗證腳本

| 腳本 | 用途 |
|------|------|
| `validate_tw_momentum.py` | M1 / M2 vs 0050，2010–今 |
| `validate_tw_entry_timing.py` | 季初直接買 vs 等回調位再買 |
| `validate_tw_false_alarm.py` | 200MA 假摔各版本比較 |
| `validate_tw_momentum_risk.py` | 動量崩潰風險分析 |
| `validate_tw_panic_deploy.py` | D 版恐慌部署 2x 槓桿驗證 |
| `validate_tw_regime_derisk.py` | Regime 降險驗證 |
| `validate_tw_value.py` | 價值篩選基準統計 |

## 測試

```bash
# Python（120 tests）
.venv/bin/python -m pytest tests/ -v

# 前端（10 tests）
cd dashboard/web && npm test
```

## Git 工作流程

- 不直接 push main，一律開分支：`feat/`、`fix/`、`chore/`
- PR → CI（pytest + vitest + lint + build）綠燈 → merge
- 合併後分支自動刪除

## 安全原則

- `.env`、`storage/`、`reports/` 皆 gitignored
- Dashboard 為唯讀 API，無任何下單端點
- 紙上帳本為虛擬持倉，不涉及實際下單
- 外部數據（API 回應）一律視為不可信輸入
- 新增套件前須確認為 PyPI/npm 正牌套件（防 typosquatting）
