"""台股紙上帳本:跟隨動量 TOP10(cap150)季調倉的虛擬持倉。

台幣計價,台股實際費制(買 0.1425%、賣 0.1425%+證交稅 0.3%)。
誠實條款:成交按最新收盤/報價,無盤口深度 — 紙上績效為實盤上界;
所有損益如實入帳,用於對帳回測期望,不是成績單。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

STATE_PATH = Path(__file__).resolve().parent.parent / "storage" / "tw_paper_state.json"
STATE_PATH_D = Path(__file__).resolve().parent.parent / "storage" / "tw_paper_d_state.json"
INITIAL_CASH = 1_000_000.0
BUY_FEE = 0.001425
SELL_FEE = 0.001425 + 0.003  # 手續費 + 證交稅

# D 版(🧪 實驗):恐慌部署參數(validate_tw_panic_deploy 驗證,
# Sharpe 1.30 vs A 1.26,MDD -34.6% vs -37.7%;n≈4 熊市事件 → 前瞻驗證中)
RESERVE_FRACTION = 0.25   # 破 200MA 時賣出的比例(騰預備金)
DEPLOY_DD = 0.20          # 0050 距 52 週高跌幅達 -20% → 部署預備金


def _load(path: Path = STATE_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"cash": INITIAL_CASH, "positions": {}, "started": None, "trades": [],
            "reserve_cash": 0.0, "exp_state": "normal"}


def _adjust_splits(state: dict) -> list[str]:
    """檢查持倉是否有未調整的股票分割,調整 shares 與 entry_price。

    以 entry_date 後發生的分割為基準;已調整過的用 last_split_adjusted
    欄位追蹤,避免重複套用。
    """
    events: list[str] = []
    for ticker, pos in list(state["positions"].items()):
        try:
            splits = yf.Ticker(ticker).splits
        except Exception:
            continue
        if splits.empty:
            continue
        entry_ts = pd.Timestamp(pos["entry_date"])
        if splits.index.tz is not None:
            entry_ts = entry_ts.tz_localize(splits.index.tz)
        recent = splits[splits.index > entry_ts]
        last_adj = pos.get("last_split_adjusted")
        if last_adj:
            # +1天:split 時間戳帶時區(如 09:00+08:00)，存的是日期(00:00)，
            # 用 > 會漏過同日的 split 導致重複套用
            adj_ts = pd.Timestamp(last_adj) + pd.Timedelta(days=1)
            if splits.index.tz is not None:
                adj_ts = adj_ts.tz_localize(splits.index.tz)
            recent = recent[recent.index >= adj_ts]
        if recent.empty:
            continue
        ratio = float(recent.prod())
        old_shares = pos["shares"]
        pos["shares"] = int(old_shares * ratio)
        pos["entry_price"] = round(pos["entry_price"] / ratio, 2)
        pos["last_split_adjusted"] = recent.index[-1].strftime("%Y-%m-%d")
        events.append(
            f"分割調整:{pos.get('name', ticker)} "
            f"{old_shares}→{pos['shares']}股, "
            f"成本 {pos['entry_price']}"
        )
    return events


def _tw_market_signal() -> dict | None:
    """0050 的 regime 與 52 週回撤(D 版狀態機輸入)。"""
    import yfinance as yf
    try:
        b50 = yf.download("0050.TW", period="2y", auto_adjust=True,
                          progress=False)["Close"]
        import pandas as pd
        if isinstance(b50, pd.DataFrame):
            b50 = b50.iloc[:, 0]
        r = b50.pct_change()
        b50 = (1 + r.mask(r.abs() > 0.11, 0.0).fillna(0.0)).cumprod() * float(b50.iloc[0])
        return {
            "below_ma200": bool(b50.iloc[-1] < b50.rolling(200).mean().iloc[-1]),
            "dd_52w": float(b50.iloc[-1] / b50.rolling(252).max().iloc[-1] - 1),
        }
    except Exception:
        return None


def _save(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1))


def process(picks: list[dict], prices: dict[str, float],
            rebalance_due: bool, state_path: Path = STATE_PATH) -> dict:
    """換倉(若季度到期或首次)+ 按市價估值。回傳帳本摘要。

    換倉為差額交易(與回測成本模型一致,只對變動部分計費):
    留任的持倉不動(不重新等權,省費用);被踢的賣出;
    新進的用釋出現金等分買入。
    """
    state = _load(state_path)
    _adjust_splits(state)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    first_run = state["started"] is None

    if rebalance_due or first_run:
        new_set = {p["ticker"] for p in picks if prices.get(p["ticker"])}

        # 賣出:不在新名單的持倉
        for t, pos in list(state["positions"].items()):
            if t in new_set:
                continue  # 留任,不動
            px = prices.get(t)
            if px is None:
                continue  # 無報價,留倉待下次
            proceeds = pos["shares"] * px * (1 - SELL_FEE)
            state["cash"] += proceeds
            state["trades"].append({
                "date": now, "side": "sell", "ticker": t,
                "name": pos.get("name", t),
                "shares": pos["shares"], "price": round(px, 2),
                "pnl_pct": round((px / pos["entry_price"] - 1) * 100, 2),
            })
            del state["positions"][t]

        # 買入:新進名單(現金等分)
        additions = [p for p in picks
                     if p["ticker"] in new_set
                     and p["ticker"] not in state["positions"]]
        if additions:
            alloc = state["cash"] / len(additions)
            for p in additions:
                px = prices[p["ticker"]]
                shares = int(alloc / (px * (1 + BUY_FEE)))  # 整股
                if shares <= 0:
                    continue
                cost = shares * px * (1 + BUY_FEE)
                state["cash"] -= cost
                state["positions"][p["ticker"]] = {
                    "shares": shares, "entry_price": px, "entry_date": now,
                    "name": p["name"],
                }
                state["trades"].append({
                    "date": now, "side": "buy", "ticker": p["ticker"],
                    "name": p["name"],
                    "shares": shares, "price": round(px, 2), "pnl_pct": None,
                })
        if first_run:
            state["started"] = now

    # 市價估值
    holdings = []
    market_value = 0.0
    for t, pos in state["positions"].items():
        px = prices.get(t, pos["entry_price"])
        value = pos["shares"] * px
        market_value += value
        holdings.append({
            "ticker": t, "name": pos.get("name", t),
            "shares": pos["shares"], "entry_price": pos["entry_price"],
            "price": round(px, 2),
            "pnl_pct": round((px / pos["entry_price"] - 1) * 100, 2),
        })
    equity = round(state["cash"] + market_value, 0)
    _save(state, state_path)

    return {
        "equity": equity,
        "cash": round(state["cash"], 0),
        "started": state["started"],
        "return_pct": round((equity / INITIAL_CASH - 1) * 100, 2),
        "holdings": sorted(holdings, key=lambda h: -h["pnl_pct"]),
        "n_trades": len(state["trades"]),
    }


def process_d(picks: list[dict], prices: dict[str, float],
              rebalance_due: bool, state_path: Path = STATE_PATH_D,
              signal: dict | None = None) -> dict:
    """🧪 D 版:A 版 + 恐慌部署狀態機。

    normal   → 0050 破 200MA:賣出各持倉 25% 入預備金(reserved)
    reserved → 52週回撤 ≤ -20%:預備金按比例加碼現有持倉(deployed,恐慌部署)
             → 未達門檻即站回 MA:同樣打回(fallback 回補,normal)
    deployed → 站回 MA:normal
    預備金鎖定,季調倉只能用自由現金。
    """
    state = _load(state_path)
    state.setdefault("reserve_cash", 0.0)
    state.setdefault("exp_state", "normal")
    _adjust_splits(state)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    events: list[str] = []

    sig = signal if signal is not None else _tw_market_signal()
    if sig:
        st = state["exp_state"]
        if st == "normal" and sig["below_ma200"]:
            for t, pos in state["positions"].items():
                px = prices.get(t)
                if px is None or pos["shares"] < 4:
                    continue
                sell_shares = int(pos["shares"] * RESERVE_FRACTION)
                if sell_shares <= 0:
                    continue
                state["reserve_cash"] += sell_shares * px * (1 - SELL_FEE)
                pos["shares"] -= sell_shares
                state["trades"].append({
                    "date": now, "side": "sell", "ticker": t,
                    "name": pos.get("name", t), "shares": sell_shares,
                    "price": round(px, 2),
                    "pnl_pct": round((px / pos["entry_price"] - 1) * 100, 2),
                    "note": "騰預備金",
                })
            state["exp_state"] = "reserved"
            events.append("🧪 D帳:0050 破 200MA — 已騰出 25% 預備金")
        elif st == "reserved":
            deploy = None
            if sig["dd_52w"] <= -DEPLOY_DD:
                deploy = "恐慌部署"
            elif not sig["below_ma200"]:
                deploy = "fallback 回補"
            if deploy:
                cash_in = state["reserve_cash"]
                state["reserve_cash"] = 0.0
                mv = {t: p["shares"] * prices.get(t, p["entry_price"])
                      for t, p in state["positions"].items()}
                total_mv = sum(mv.values()) or 1.0
                for t, pos in state["positions"].items():
                    px = prices.get(t)
                    if px is None:
                        continue
                    budget = cash_in * mv[t] / total_mv
                    add = int(budget / (px * (1 + BUY_FEE)))
                    if add <= 0:
                        continue
                    cost = add * px * (1 + BUY_FEE)
                    cash_in -= cost
                    # 加碼後進場價按加權平均更新
                    old_cost = pos["shares"] * pos["entry_price"]
                    pos["shares"] += add
                    pos["entry_price"] = round(
                        (old_cost + add * px) / pos["shares"], 2)
                    state["trades"].append({
                        "date": now, "side": "buy", "ticker": t,
                        "name": pos.get("name", t), "shares": add,
                        "price": round(px, 2), "pnl_pct": None, "note": deploy,
                    })
                state["cash"] += cash_in  # 加碼找零回自由現金
                state["exp_state"] = "deployed" if deploy == "恐慌部署" else "normal"
                events.append(f"🧪 D帳:{deploy}(52週回撤 {sig['dd_52w']:.0%})")
        elif st == "deployed" and not sig["below_ma200"]:
            state["exp_state"] = "normal"

    _save(state, state_path)
    # 常規差額換倉 + 估值(共用主邏輯;預備金不在 cash 內,天然鎖定)
    out = process(picks, prices, rebalance_due, state_path=state_path)
    final = _load(state_path)
    out["equity"] = round(out["equity"] + final.get("reserve_cash", 0.0), 0)
    out["reserve_cash"] = round(final.get("reserve_cash", 0.0), 0)
    out["exp_state"] = final.get("exp_state", "normal")
    out["return_pct"] = round((out["equity"] / INITIAL_CASH - 1) * 100, 2)
    out["events"] = events
    return out
