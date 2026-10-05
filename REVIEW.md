# Code Review 標準 — Trading System

執行 code review 時遵循此文件。Review 只交付報告，不動手改 code。

## Review 觸發方式

```
/code-review
# 或指定 base
/code-review main
```

## 三軸 Review

每次 review 沿三個軸檢查，各自獨立打分：

### 軸一：Standards（程式碼標準）

這個 code 有沒有遵守本 repo 的規範？

| 檢查項 | 判定標準 |
|--------|---------|
| TDD | 有新功能/bug fix 是否附帶測試？測試先寫還是後補？ |
| 安全 | `.env` 有沒有洩漏？外部輸入有沒有驗證？`eval`/`exec`？ |
| 分離 | 策略層是否只產生訊號？有沒有混入執行邏輯？ |
| 回測誠實 | fee_rate / slippage > 0？signal shift(1)？ |
| 前視偏差 | 有沒有用未來數據？（常見：忘了 shift、用 iloc[-1] 當訊號） |
| 浮點衛生 | yfinance 的 float 有沒有 round？price 顯示是否乾淨？ |
| 帳本一致 | state JSON 的 shares / entry_price / cash 有沒有漏更新？股票分割有處理？ |
| Git | 有沒有直接 push main？branch 命名對嗎？commit message 有意義嗎？ |

### 軸二：Spec（規格符合）

這個 code 有沒有做到 issue / PRD 要求的事？

- 對照 PR description 或 issue，逐條檢查功能是否完成
- 有沒有漏掉的 edge case（空資料、分割、除權、假日無報價）
- 有沒有做多餘的事（scope creep）

### 軸三：Behavior（行為保持，限重構）

重構時專用：新 code 的行為是否與舊 code 一致？

- 每個行為差異必須是「宣告的改變」（在 PR 裡說明）
- 未宣告的行為差異 = bug
- 常見陷阱：重構 tw_paper.py 時忘了保留 `_adjust_splits()` 呼叫

## Review 報告格式

```markdown
## Review: [PR title]

### Standards
| 項目 | ✅/⚠️/❌ | 說明 |
|------|---------|------|
| TDD  | ✅      | 4 個新測試，先寫後實作 |
| ...  | ...     | ...  |

### Spec
- ✅ 功能 A：已實作，測試覆蓋
- ⚠️ 功能 B：實作了但缺 edge case（空名單）
- ❌ 功能 C：未實作

### Behavior（僅限重構 PR）
- ✅ 行為一致
- ⚠️ 未宣告差異：xxx

### 總結
[一句話結論：approve / request changes / 需要討論]

### 建議修法（僅供參考，不代做）
1. [具體建議，含檔案和行號]
```

## 特別注意事項

### 台股特有 edge cases
- **股票分割 / 除權**：tw_paper.py 的 `_adjust_splits()` 有沒有覆蓋？
- **假日無報價**：`prices.get(t, pos["entry_price"])` 的 fallback 會不會掩蓋真實損益？
- **漲跌停清洗**：`ret.abs() > 0.11` 的門檻是台股 10% 漲跌幅 + 1% 容差
- **TWO 後綴**：上櫃股代號是 `.TWO`，顯示時要 `.replace(/\.TWO?$/, "")`

### Dashboard 相關
- API 是唯讀的（GET only + 偏好 PUT），有沒有誤加寫入端點？
- 報告檔（reports/）是靜態快照，改了 state 不會自動更新報告
- 前端 build 後要 `launchctl kickstart` 重啟 dashboard

### 回測相關
- 新策略有沒有跟 0050 B&H 做對照組？
- 有沒有標注生存者偏差的影響？
- 參數是全樣本最佳化還是 walk-forward？
