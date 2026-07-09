"""美股研究掃描(每週):python scripts/us_screener.py

輸出 reports/us_screen_YYYY-MM-DD.json + Discord 摘要。
研究工具 — 無模型選股宣稱(美股動量已驗證否決)。
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.us_screen import SECTOR_OF, TIER2, UNIVERSE, market_snapshot, spy_state
from data.value_screen import fetch_metrics
from monitoring.notify import send

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

if __name__ == "__main__":
    momentum, tech = market_snapshot()

    rows = []
    for ticker, name in UNIVERSE.items():
        m = fetch_metrics(ticker)
        if m is None:
            continue
        m["name"] = name
        m["sector"] = SECTOR_OF.get(ticker, "其他")
        m["tier"] = 2 if ticker in TIER2 else 1
        m["momentum_pct"] = momentum.get(ticker)
        t = tech.get(ticker)
        if t:
            m["range_pos_20d"] = t["range_pos_20d"]
            m["zone"] = t["zone"]
        rows.append(m)
    rows.sort(key=lambda r: -(r.get("momentum_pct") or -999))

    result = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "universe_size": len(UNIVERSE),
        "fetched": len(rows),
        "rows": rows,
        "spy_state": spy_state(),
    }
    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"us_screen_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print(f"美股池 {len(UNIVERSE)} 檔,取得 {len(rows)}。報告: {out}")

    s = result["spy_state"]
    lines = [f"## 🇺🇸 美股研究掃描(週報){datetime.now(timezone.utc):%Y-%m-%d}"]
    if s:
        lines.append(f"SPY {'🟢' if s['regime_on'] else '🔴'} 200MA "
                     f"{s['pct_vs_ma200']:+}%・近12月 {s['heat_12m_pct']:+.0f}%")
    zone_mark = {"pullback": "🟢", "mid": "⚪", "high": "🔴"}
    top = [r for r in rows if r.get("momentum_pct") is not None][:15]
    trows = ["代號    名稱          動量     位置"]
    for r in top:
        z = zone_mark.get(r.get("zone", ""), " ")
        trows.append(f"{r['ticker']:<7}{r['name']:　<7}"
                     f"{r['momentum_pct']:>+7.1f}%  {z}{r.get('range_pos_20d', '—')}%")
    lines.append("```\n" + "\n".join(trows) + "\n```")
    lines.append("> 研究瀏覽,無模型選股(美股動量驗證未過)")
    send("\n".join(lines))
