"""台股價值篩選(每週):python scripts/value_screener.py

輸出 reports/value_screen_YYYY-MM-DD.json + Discord 週報。
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.value_screen import screen
from monitoring.notify import send

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

if __name__ == "__main__":
    result = screen()
    result["scanned_at"] = datetime.now(timezone.utc).isoformat()

    # 動量模型(取代舊的殖利率三關作為選股標記):
    # ✅ = 12-1 動量 TOP10;表格按動量排序;財報欄位降為參考資訊
    from data.tw_momentum import (current_picks, forward_performance,
                                  momentum_all, update_tracking)
    momentum = momentum_all()
    picks = current_picks(momentum)
    picked_set = {p["ticker"] for p in picks}
    for r in result["rows"]:
        r["momentum_pct"] = momentum.get(r["ticker"])
        r["picked"] = r["ticker"] in picked_set
    result["rows"].sort(key=lambda r: -(r.get("momentum_pct") or -999))

    rebalanced = update_tracking(picks)
    result["momentum"] = {
        "picks": picks,
        "rebalanced": rebalanced,
        "performance": forward_performance(),
    }

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"value_screen_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1))

    m = result["momentum"]
    picked_rows = [r for r in result["rows"] if r["picked"]]
    print(f"股票池 {result['universe_size']} 檔,動量 TOP{len(picked_rows)} 已選")

    lines = [f"## 📈 台股動量 TOP10(週報){datetime.now(timezone.utc):%Y-%m-%d}"
             + (" — 本週調倉" if m["rebalanced"] else "")]
    rows = ["代號      名稱       動量    殖利率  營收成長   PE"]
    for r in picked_rows:
        dy = f"{r['dividend_yield']}%" if r["dividend_yield"] is not None else "—"
        rg = f"{r['revenue_growth']:+.1f}%" if r["revenue_growth"] is not None else "—"
        rows.append(
            f"{r['ticker'].replace('.TW','').replace('.TWO',''):<6}"
            f"{r['name']:　<5}"
            f"{r['momentum_pct']:>+7.1f}%  {dy:>6}  {rg:>7}  "
            f"{r['pe'] if r['pe'] else '—':>5}")
    lines.append("```\n" + "\n".join(rows) + "\n```")
    perf = m["performance"]
    if perf and perf["n_rebalances"] > 1:
        lines.append(f"前瞻績效(自 {perf['since']}):策略 {perf['strategy_pct']:+}% "
                     f"vs 0050 {perf['bench_0050_pct']:+}%")
    send("\n".join(lines))
    print(f"報告: {out}")
