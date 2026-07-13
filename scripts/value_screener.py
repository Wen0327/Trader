"""台股價值篩選(每週):python scripts/value_screener.py

輸出 reports/value_screen_YYYY-MM-DD.json + Discord 週報。
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.value_screen import screen
from monitoring.notify import alert_on_crash, send

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
alert_on_crash("台股週掃")

if __name__ == "__main__":
    result = screen()
    result["scanned_at"] = datetime.now(timezone.utc).isoformat()

    # 動量模型(取代舊的殖利率三關作為選股標記):
    # ✅ = 12-1 動量 TOP10;表格按動量排序;財報欄位降為參考資訊
    from data.tw_momentum import (current_picks, forward_performance,
                                  market_snapshot, update_tracking)
    momentum, tech = market_snapshot()
    picks = current_picks(momentum)
    picked_set = {p["ticker"] for p in picks}
    for r in result["rows"]:
        r["momentum_pct"] = momentum.get(r["ticker"])
        r["picked"] = r["ticker"] in picked_set
        t = tech.get(r["ticker"])
        if t:
            r["range_pos_20d"] = t["range_pos_20d"]
            r["zone"] = t["zone"]
    # 通過模型者(✅)排最前,其餘按動量遞減(被 cap 剔除的拋物線沉底部前段)
    result["rows"].sort(key=lambda r: (not r["picked"],
                                       -(r.get("momentum_pct") or -999)))

    rebalanced = update_tracking(picks)
    result["momentum"] = {
        "picks": picks,
        "rebalanced": rebalanced,
        "performance": forward_performance(),
    }

    # 紙上帳本:A 標準版 + 🧪 D 恐慌部署實驗版,平行記帳
    from data.tw_paper import process as paper_process
    from data.tw_paper import process_d
    from monitoring import equity_log
    prices = {r["ticker"]: r["price"] for r in result["rows"] if r.get("price")}
    result["paper"] = paper_process(picks, prices, rebalanced)
    equity_log.record("paper_tw", result["paper"]["equity"])
    result["paper_d"] = process_d(picks, prices, rebalanced)
    equity_log.record("paper_tw_d", result["paper_d"]["equity"])
    if result["paper_d"]["events"]:
        send("\n".join(result["paper_d"]["events"]))

    m = result["momentum"]
    picked_rows = [r for r in result["rows"] if r["picked"]]
    print(f"股票池 {result['universe_size']} 檔,動量 TOP{len(picked_rows)} 已選")

    lines = [f"## 📈 台股動量 TOP10(週報){datetime.now(timezone.utc):%Y-%m-%d}"
             + (" — 本週調倉" if m["rebalanced"] else "")]
    # 只列名單,數據欄看儀表板即可(2026-07-13 使用者要求精簡)
    # 注意順序:先 .TWO 再 .TW,否則 3529.TWO 會被咬成 3529O
    rows = [f"{r['ticker'].replace('.TWO', '').replace('.TW', ''):<6}{r['name']}"
            for r in picked_rows]
    lines.append("```\n" + "\n".join(rows) + "\n```")
    perf = m["performance"]
    if perf and perf["n_rebalances"] > 1:
        lines.append(f"前瞻績效(自 {perf['since']}):策略 {perf['strategy_pct']:+}% "
                     f"vs 0050 {perf['bench_0050_pct']:+}%")

    from data.tw_momentum import market_state
    state = market_state()
    if state:
        result["market_state"] = state
        lines.append(
            f"市場狀態:0050 {'🟢' if state['regime_on'] else '🔴'} 200MA "
            f"{state['pct_vs_ma200']:+}%・近12月 {state['heat_12m_pct']:+.0f}%"
            f"({state['bucket']})→ 歷史同狀態下一季:"
            f"平均 {state['bucket_next_q_avg']:+}%・勝率 {state['bucket_win_rate']}%")

    # 報告落地必須在所有欄位(含 market_state)就緒之後
    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"value_screen_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1))

    send("\n".join(lines))
    print(f"報告: {out}")
