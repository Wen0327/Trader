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

    # 動量前瞻追蹤(季調倉快照 + 累積績效對帳)
    from data.tw_momentum import current_picks, forward_performance, update_tracking
    picks = current_picks()
    rebalanced = update_tracking(picks)
    result["momentum"] = {
        "picks": picks,
        "rebalanced": rebalanced,
        "performance": forward_performance(),
    }

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"value_screen_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1))

    passed = [r for r in result["rows"] if r["passed"]]
    print(f"股票池 {result['universe_size']} 檔,取得 {result['fetched']},"
          f"通過 {len(passed)}")

    lines = [f"## 💰 台股價值篩選(週報){datetime.now(timezone.utc):%Y-%m-%d}",
             f"通過 {len(passed)}/{result['fetched']}(殖利率≥3%・營收成長≥0・獲利中)"]
    if passed:
        rows = ["代號      名稱      殖利率  營收成長  獲利率   PE"]
        for r in passed[:15]:
            rows.append(
                f"{r['ticker'].replace('.TW',''):<6}"
                f"{r['name']:　<5}"
                f"{r['dividend_yield']:>5.1f}%  "
                f"{r['revenue_growth']:>+6.1f}%  "
                f"{r['profit_margin']:>5.1f}%  "
                f"{r['pe'] if r['pe'] else '—':>5}")
        lines.append("```\n" + "\n".join(rows) + "\n```")
        if len(passed) > 15:
            lines.append(f"…另有 {len(passed) - 15} 檔,見儀表板")

    m = result["momentum"]
    lines.append(f"\n**📈 動量 TOP10**(前瞻追蹤中{',本週調倉' if m['rebalanced'] else ''})")
    mrows = [f"{p['ticker'].replace('.TW','').replace('O',''):<6}{p['name']:　<5}"
             f"動量 {p['momentum_pct']:>+6.1f}%" for p in m["picks"]]
    lines.append("```\n" + "\n".join(mrows) + "\n```")
    perf = m["performance"]
    if perf and perf["n_rebalances"] > 1:
        lines.append(f"前瞻績效(自 {perf['since']}):策略 {perf['strategy_pct']:+}% "
                     f"vs 0050 {perf['bench_0050_pct']:+}%")
    send("\n".join(lines))
    print(f"報告: {out}")
