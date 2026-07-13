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

# 判定閾值:重疊區 close 比值
IDENTICAL_TOL = 1e-6     # 視為一致
CONSTANT_RATIO_TOL = 1e-4  # 比值變異係數低於此 → 恆定比例(調整因子)


@dataclass
class MergeResult:
    merged: pd.DataFrame
    action: str            # "append" | "rescaled" | "conflict"
    factor: float | None = None


def merge_bars(stored: pd.DataFrame | None, fresh: pd.DataFrame) -> MergeResult:
    """以重疊區比對決定合併策略。

    一致 → append 新棒;恆定比例差 → 本地全歷史重刻(除權息/分割);
    非恆定差 → conflict,原樣退回不動數據(交由呼叫端告警)。
    """
    if stored is None or stored.empty:
        return MergeResult(fresh.sort_index(), "append")

    common = stored.index.intersection(fresh.index)
    if len(common) == 0:
        merged = pd.concat([stored, fresh]).sort_index()
        return MergeResult(merged[~merged.index.duplicated(keep="last")], "append")

    ratio = fresh.loc[common, "close"] / stored.loc[common, "close"]
    if (ratio - 1).abs().max() < IDENTICAL_TOL:
        merged = pd.concat([stored, fresh]).sort_index()
        return MergeResult(merged[~merged.index.duplicated(keep="last")], "append")

    if len(ratio) > 1 and float(ratio.std() / ratio.mean()) < CONSTANT_RATIO_TOL:
        factor = float(ratio.mean())
        rescaled = stored.copy()
        rescaled[PRICE_COLS] = rescaled[PRICE_COLS] * factor  # 量不縮放
        merged = pd.concat([rescaled, fresh]).sort_index()
        return MergeResult(merged[~merged.index.duplicated(keep="last")],
                           "rescaled", factor)

    return MergeResult(stored, "conflict")


def load(ticker: str) -> pd.DataFrame | None:
    path = STORE_DIR / f"{ticker}_5m.parquet"
    return pd.read_parquet(path) if path.exists() else None


def save(ticker: str, df: pd.DataFrame) -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(STORE_DIR / f"{ticker}_5m.parquet")
