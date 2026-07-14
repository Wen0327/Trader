"""分鐘數據本地累積:5m parquet 存檔 + 重疊比對調整。

為什麼要存:Yahoo 分鐘級只回溯 60 天,今天不存以後回填不了。
日內策略研究(backlog)需要長歷史,數據有時間價值,先累積。

為什麼用重疊比對而非事件清單:除權息/分割後 Yahoo 整段重調,
事件清單(Ticker.splits)登記可能延遲/遺漏,且無法驗證自算因子
與 Yahoo 實際套用是否一致;重疊區直接量測實際因子,自帶驗證,
還能抓到數據修正(0050 假 -75%、SPCX 假歷史的前科)。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

STORE_DIR = Path(__file__).resolve().parent.parent / "storage" / "intraday"
PRICE_COLS = ["open", "high", "low", "close"]

# 判定閾值(2026-07-14 事故校正):Yahoo 浮點抖動 ≤1e-5、
# 真實除權息因子 ≥1e-3,中間差百倍,1e-3 乾淨切開
NOISE_TOL = 1e-3
CONSTANT_RATIO_TOL = 1e-4  # 不一致段比值變異係數低於此 → 恆定(調整因子)
HEAL_MAX_BARS = 2          # 少量內部棒不一致 → 活棒定稿,以 fresh 為準自癒

BAR = pd.Timedelta(minutes=5)


@dataclass
class MergeResult:
    merged: pd.DataFrame
    action: str            # "append" | "rescaled" | "healed" | "conflict"
    factor: float | None = None


def drop_live_bar(df: pd.DataFrame,
                  now: pd.Timestamp | None = None) -> pd.DataFrame:
    """丟掉尚未收完的最後一根活棒(盤中抓取時存暫值,定稿後必然對不上)。"""
    now = now or pd.Timestamp.now(tz="UTC")
    return df[df.index + BAR <= now]


def merge_bars(stored: pd.DataFrame | None, fresh: pd.DataFrame) -> MergeResult:
    """以重疊區比對決定合併策略(重疊區一律以 fresh 為準去重)。

    - 一致(差 < NOISE_TOL,容浮點抖動)→ append
    - 不一致段為「前綴 + 恆定比例」→ 除權息/分割:重刻該時點前的
      本地歷史(含重疊窗之前的舊棒);盤中除息(窗中段)也涵蓋
    - 少量(≤HEAL_MAX_BARS)內部棒不一致 → 活棒定稿,自癒
      (但不一致含窗首除外——窗外歷史可能也要重刻,不得蒙混)
    - 其餘 → conflict,原樣退回不動數據(交由呼叫端告警)
    """
    if stored is None or stored.empty:
        return MergeResult(fresh.sort_index(), "append")

    def _append(base: pd.DataFrame, action: str,
                factor: float | None = None) -> MergeResult:
        merged = pd.concat([base, fresh]).sort_index()
        return MergeResult(merged[~merged.index.duplicated(keep="last")],
                           action, factor)

    common = stored.index.intersection(fresh.index).sort_values()
    if len(common) == 0:
        return _append(stored, "append")

    ratio = fresh.loc[common, "close"] / stored.loc[common, "close"]
    mismatch = (ratio - 1).abs() >= NOISE_TOL
    if not mismatch.any():
        return _append(stored, "append")

    m = mismatch.to_numpy()
    # 前綴形態:從窗首開始連續不一致、之後全一致(全窗不一致亦屬之)
    # = 布林序列單調不升
    is_prefix = bool(m[0]) and all(int(m[i]) >= int(m[i + 1])
                                   for i in range(len(m) - 1))
    mis_ratio = ratio[mismatch]
    constant = (len(mis_ratio) == 1
                or float(mis_ratio.std() / mis_ratio.mean()) < CONSTANT_RATIO_TOL)

    if is_prefix and constant:
        factor = float(mis_ratio.mean())
        cutoff = common[m.nonzero()[0][-1]]  # 最後一根不一致的時間
        rescaled = stored.copy()
        sel = rescaled.index <= cutoff
        rescaled.loc[sel, PRICE_COLS] = rescaled.loc[sel, PRICE_COLS] * factor
        return _append(rescaled, "rescaled", factor)

    if int(mismatch.sum()) <= HEAL_MAX_BARS and not bool(m[0]):
        return _append(stored, "healed")  # keep="last" → fresh 定稿蓋掉暫值

    return MergeResult(stored, "conflict")


def load(ticker: str) -> pd.DataFrame | None:
    path = STORE_DIR / f"{ticker}_5m.parquet"
    return pd.read_parquet(path) if path.exists() else None


def save(ticker: str, df: pd.DataFrame) -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(STORE_DIR / f"{ticker}_5m.parquet")
