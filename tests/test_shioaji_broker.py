"""Shioaji broker:登入、下單、持倉查詢、對帳。全部 mock,不打真實 API。"""

import json
from unittest.mock import MagicMock, patch

import pytest

from execution.shioaji_broker import (
    BrokerError,
    ShioajiBroker,
    reconcile,
)


# ── helpers ──────────────────────────────────────────────

def _mock_api(simulation: bool = True):
    api = MagicMock()
    api.stock_account = MagicMock()
    api.simulation = simulation
    return api


def _make_contract(code: str = "2330"):
    c = MagicMock()
    c.code = code
    return c


def _make_position(code: str, quantity: int, avg_price: float, last_price: float):
    p = MagicMock()
    p.code = code
    p.quantity = quantity
    p.avg_price = avg_price
    p.last_price = last_price
    p.pnl = round((last_price - avg_price) * quantity * 1000, 2)
    return p


# ── 登入 ─────────────────────────────────────────────────

class TestLogin:
    def test_simulation_mode_no_ca(self):
        with patch("execution.shioaji_broker.sj") as mock_sj:
            mock_sj.Shioaji.return_value = _mock_api(simulation=True)
            broker = ShioajiBroker(
                api_key="test_key", secret_key="test_secret", simulation=True,
            )
        assert broker.simulation is True
        # simulation 模式不需要 activate_ca
        broker.api.activate_ca.assert_not_called()

    def test_production_requires_ca(self):
        with patch("execution.shioaji_broker.sj") as mock_sj:
            mock_sj.Shioaji.return_value = _mock_api(simulation=False)
            broker = ShioajiBroker(
                api_key="key", secret_key="secret", simulation=False,
                ca_path="/path/to/cert.pfx", ca_passwd="pass", person_id="A123456789",
            )
        broker.api.activate_ca.assert_called_once_with(
            ca_path="/path/to/cert.pfx",
            ca_passwd="pass",
            person_id="A123456789",
        )

    def test_production_without_ca_raises(self):
        with patch("execution.shioaji_broker.sj") as mock_sj:
            mock_sj.Shioaji.return_value = _mock_api(simulation=False)
            with pytest.raises(BrokerError, match="CA"):
                ShioajiBroker(
                    api_key="key", secret_key="secret", simulation=False,
                )


# ── 下單 ─────────────────────────────────────────────────

class TestPlaceOrder:
    def test_buy_creates_correct_order(self):
        with patch("execution.shioaji_broker.sj") as mock_sj:
            mock_sj.Shioaji.return_value = _mock_api()
            mock_sj.Action.Buy = "Buy"
            mock_sj.StockPriceType.LMT = "LMT"
            mock_sj.OrderType.ROD = "ROD"
            mock_sj.StockOrderLot.Common = "Common"
            mock_sj.StockOrderCond.Cash = "Cash"
            broker = ShioajiBroker(api_key="k", secret_key="s", simulation=True)

            contract = _make_contract("2330")
            broker.api.contracts.get.return_value = contract

            broker.buy("2330", price=580.0, lots=1)

        broker.api.place_order.assert_called_once()
        args = broker.api.place_order.call_args
        assert args[0][0] == contract  # first arg = contract

    def test_sell_uses_sell_action(self):
        with patch("execution.shioaji_broker.sj") as mock_sj:
            mock_sj.Shioaji.return_value = _mock_api()
            mock_sj.Action.Sell = "Sell"
            mock_sj.StockPriceType.LMT = "LMT"
            mock_sj.OrderType.ROD = "ROD"
            mock_sj.StockOrderLot.Common = "Common"
            mock_sj.StockOrderCond.Cash = "Cash"
            broker = ShioajiBroker(api_key="k", secret_key="s", simulation=True)
            broker.api.contracts.get.return_value = _make_contract("2317")

            broker.sell("2317", price=250.0, lots=2)

        # 驗證 StockOrder 被呼叫時 action 參數是 Sell
        mock_sj.StockOrder.assert_called_once()
        call_kwargs = mock_sj.StockOrder.call_args[1]
        assert call_kwargs["action"] == "Sell"
        assert call_kwargs["quantity"] == 2

    def test_invalid_ticker_raises(self):
        with patch("execution.shioaji_broker.sj") as mock_sj:
            mock_sj.Shioaji.return_value = _mock_api()
            broker = ShioajiBroker(api_key="k", secret_key="s", simulation=True)
            broker.api.contracts.get.return_value = None

            with pytest.raises(BrokerError, match="找不到"):
                broker.buy("INVALID", price=100, lots=1)


# ── 持倉查詢 ─────────────────────────────────────────────

class TestPositions:
    def test_returns_dict(self):
        with patch("execution.shioaji_broker.sj") as mock_sj:
            mock_sj.Shioaji.return_value = _mock_api()
            broker = ShioajiBroker(api_key="k", secret_key="s", simulation=True)
            broker.api.list_positions.return_value = [
                _make_position("2330", 2, 580.0, 600.0),
                _make_position("2317", 1, 250.0, 240.0),
            ]
            pos = broker.positions()

        assert pos["2330"]["lots"] == 2
        assert pos["2330"]["avg_price"] == 580.0
        assert pos["2317"]["lots"] == 1

    def test_empty_positions(self):
        with patch("execution.shioaji_broker.sj") as mock_sj:
            mock_sj.Shioaji.return_value = _mock_api()
            broker = ShioajiBroker(api_key="k", secret_key="s", simulation=True)
            broker.api.list_positions.return_value = []
            assert broker.positions() == {}


# ── 對帳 ─────────────────────────────────────────────────

class TestReconcile:
    def test_matching_positions(self):
        broker_pos = {
            "2330": {"lots": 1, "avg_price": 580.0},
        }
        paper_pos = {
            "2330.TW": {"shares": 1000, "entry_price": 580.0},
        }
        diffs = reconcile(broker_pos, paper_pos)
        assert diffs == []

    def test_quantity_mismatch(self):
        broker_pos = {"2330": {"lots": 2, "avg_price": 580.0}}
        paper_pos = {"2330.TW": {"shares": 1000, "entry_price": 580.0}}
        diffs = reconcile(broker_pos, paper_pos)
        assert len(diffs) == 1
        assert "2330" in diffs[0]

    def test_missing_in_broker(self):
        broker_pos = {}
        paper_pos = {"2330.TW": {"shares": 1000, "entry_price": 580.0}}
        diffs = reconcile(broker_pos, paper_pos)
        assert len(diffs) == 1

    def test_extra_in_broker(self):
        broker_pos = {"2330": {"lots": 1, "avg_price": 580.0}}
        paper_pos = {}
        diffs = reconcile(broker_pos, paper_pos)
        assert len(diffs) == 1
