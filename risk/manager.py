"""風控層:所有訂單的必經關卡(硬邊界,策略層不得繞過)。

規則:
1. 單筆訂單金額上限(佔帳戶權益比例)
2. 單一標的總持倉上限
3. 日虧損 kill switch:當日權益回撤超過閾值 → 拒絕所有新開倉,只允許減倉
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


class RiskViolation(Exception):
    """訂單違反風控規則。"""


@dataclass
class RiskConfig:
    max_order_pct: float = 0.10        # 單筆訂單 ≤ 帳戶權益 10%
    max_position_pct: float = 0.30     # 單一標的持倉 ≤ 帳戶權益 30%
    daily_max_drawdown: float = 0.05   # 當日回撤 5% 觸發 kill switch


@dataclass
class RiskManager:
    config: RiskConfig = field(default_factory=RiskConfig)
    _day_start_equity: float | None = None
    _day: date | None = None
    _killed: bool = False

    def to_dict(self) -> dict:
        """序列化當日狀態,供 bot 重啟後恢復。"""
        return {
            "day": self._day.isoformat() if self._day else None,
            "day_start_equity": self._day_start_equity,
            "killed": self._killed,
        }

    def restore(self, state: dict) -> None:
        if not state or not state.get("day"):
            return
        self._day = datetime.fromisoformat(state["day"]).date()
        self._day_start_equity = state.get("day_start_equity")
        self._killed = bool(state.get("killed", False))

    def update_equity(self, equity: float) -> None:
        """每次循環回報最新帳戶權益(USDT 計價)。"""
        today = date.today()
        if self._day != today:
            self._day = today
            self._day_start_equity = equity
            self._killed = False  # 新的一天重置
        if self._day_start_equity and self._day_start_equity > 0:
            drawdown = equity / self._day_start_equity - 1
            if drawdown < -self.config.daily_max_drawdown:
                self._killed = True

    @property
    def kill_switch_active(self) -> bool:
        return self._killed

    def check_order(
        self,
        side: str,
        order_value: float,       # 本筆訂單金額(USDT)
        current_position_value: float,  # 該標的現有持倉市值(USDT)
        equity: float,            # 帳戶總權益(USDT)
    ) -> None:
        """通過 = 無事,違規 = raise RiskViolation。"""
        self.update_equity(equity)

        if self._killed and side == "buy":
            raise RiskViolation(
                f"Kill switch 已觸發(當日回撤超過 "
                f"{self.config.daily_max_drawdown:.0%}),拒絕新開倉"
            )

        if order_value > equity * self.config.max_order_pct:
            raise RiskViolation(
                f"單筆訂單 {order_value:.2f} USDT 超過上限 "
                f"{equity * self.config.max_order_pct:.2f} USDT "
                f"(權益 {self.config.max_order_pct:.0%})"
            )

        if side == "buy":
            new_position = current_position_value + order_value
            if new_position > equity * self.config.max_position_pct:
                raise RiskViolation(
                    f"持倉將達 {new_position:.2f} USDT,超過單一標的上限 "
                    f"{equity * self.config.max_position_pct:.2f} USDT "
                    f"(權益 {self.config.max_position_pct:.0%})"
                )
