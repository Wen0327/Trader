"""每日盤前進場參考簡報(Discord)。

與 transitions(僅變化時通知)不同,簡報每日固定發送:
有效訊號的停損結構、等確認標的的觸發價位、比值狀態。
內容為系統數據整理,恆附免責聲明。
"""

from __future__ import annotations

from datetime import datetime, timezone

GRADE_ZH = {"strong": "強", "mid": "中", "weak": "弱"}


def _exit_level(w: dict) -> float | None:
    pct = w.get("pct_to_exit")
    return w["price"] / (1 + pct / 100) if pct is not None else None


def _gate_level(w: dict, pct_key: str) -> float | None:
    pct = w.get(pct_key)
    return w["price"] / (1 + pct / 100) if pct is not None else None


def compose(rotation: dict) -> str:
    """Discord markdown 排版:標題 + 等寬 code block 對齊表格。"""
    wl = rotation.get("watchlist", [])
    active = [w for w in wl if w.get("status_rank") == 4]
    near = [w for w in wl if w.get("status_rank") == 3]
    passed = [w for w in wl if w.get("status_rank") == 2]
    below = [w for w in wl if w.get("status_rank", 0) <= 1]

    lines = [f"## 📋 盤前簡報 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"]

    ratios = rotation.get("ratios", [])
    if ratios:
        lines.append("**輪動比值**  " + "　".join(
            f"{r['pair']} {'🟢' if r['rotation_on'] else '⚪'} "
            f"`{r['pct_vs_ma200']:+.1f}%`" for r in ratios))

    def gated(items):
        """驗證閘門:通過者才有進場框架資格。"""
        return ([w for w in items if w.get("edge_passed")],
                [w for w in items if not w.get("edge_passed")])

    below_waiting = [w for w in below if w.get("status_rank") == 1]
    active_ok, _ = gated(active)
    waiting_ok, _ = gated(near + passed + below_waiting)

    if active_ok:
        lines.append("\n**✅ 進場參考**(通過每日 edge 驗證)— 停損設 20 日低,倉位按停損距離縮")
        rows = ["標的    現價     停損價   進場至今"]
        for w in active_ok:
            exit_lv = _exit_level(w)
            grade = GRADE_ZH.get(w.get("signal_grade", ""), "?")
            rows.append(
                f"{w['ticker']:<6}{w['price']:>8.2f}  {exit_lv:>7.2f}  "
                f"{w.get('since_entry_pct'):>+5.1f}%  [{grade}] "
                f"edge {w.get('edge_score')}")
        lines.append("```\n" + "\n".join(rows) + "\n```")
        weak = [w["ticker"] for w in active_ok if w.get("signal_grade") == "weak"]
        if weak:
            lines.append(f"> ⚠️ {', '.join(weak)} 瀕死訊號(貼近停損 + 水下),不建議追")
    else:
        lines.append("\n**✅ 進場參考:今日無** — 沒有任何「訊號有效 + 通過 edge 驗證」的標的")

    waiting_ok_rows = []
    for w in waiting_ok:
        if w.get("status_rank") == 1:  # 尚在 200MA 下:第一道門價位
            ma = _gate_level(w, "pct_vs_ma200")
            waiting_ok_rows.append(
                f"{w['ticker']:<6}站回 200MA  {ma:>7.2f}  還差 {abs(w['pct_vs_ma200']):>4.1f}%"
                f"  edge {w.get('edge_score')}")
        else:
            trigger = _gate_level(w, "pct_to_55d_high")
            waiting_ok_rows.append(
                f"{w['ticker']:<6}突破 55日高 {trigger:>7.2f}  還差 {abs(w['pct_to_55d_high']):>4.1f}%"
                f"  edge {w.get('edge_score')}")
    if waiting_ok_rows:
        lines.append("**⏳ 等確認**(通過驗證,突破日 = 進場點)")
        lines.append("```\n" + "\n".join(waiting_ok_rows) + "\n```")

    return "\n".join(lines)
