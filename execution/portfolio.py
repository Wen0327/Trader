"""持倉狀態持久化:追蹤「策略管理的倉位」(與 testnet 贈送資產區隔)。

同時保存風控的當日狀態(day-start equity / kill switch),
讓 bot 重啟後風控不會失憶。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "storage" / "bot_state.json"


@dataclass
class Position:
    amount: float = 0.0
    entry_price: float = 0.0


@dataclass
class Portfolio:
    positions: dict[str, Position] = field(default_factory=dict)
    risk_state: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Portfolio":
        if not STATE_PATH.exists():
            return cls()
        data = json.loads(STATE_PATH.read_text())
        positions = {
            sym: Position(**pos) for sym, pos in data.get("positions", {}).items()
        }
        return cls(positions=positions, risk_state=data.get("risk_state", {}))

    def save(self) -> None:
        STATE_PATH.parent.mkdir(exist_ok=True)
        data = {
            "positions": {
                sym: {"amount": p.amount, "entry_price": p.entry_price}
                for sym, p in self.positions.items()
                if p.amount > 0
            },
            "risk_state": self.risk_state,
        }
        STATE_PATH.write_text(json.dumps(data, indent=2))

    def get(self, symbol: str) -> Position:
        return self.positions.get(symbol, Position())

    def set(self, symbol: str, amount: float, entry_price: float) -> None:
        self.positions[symbol] = Position(amount=amount, entry_price=entry_price)

    def clear(self, symbol: str) -> None:
        self.positions.pop(symbol, None)
