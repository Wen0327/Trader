"""QQQB 紙上撮合引擎:費用、滑價、現金防護、精度捨去。"""

import pytest

from execution.paper_broker import FEE, INITIAL_CASH, SLIPPAGE, PaperBroker


def make(tmp_path, price=100.0):
    return PaperBroker(lambda s: price, cash_path=tmp_path / "cash.json")


class TestFills:
    def test_buy_charges_slippage_and_fee(self, tmp_path):
        b = make(tmp_path)
        r = b.market_order("X/USDT", "buy", 10.0)
        assert r.avg_price == pytest.approx(100.0 * (1 + SLIPPAGE))
        expected_cash = INITIAL_CASH - r.avg_price * 10 * (1 + FEE)
        assert b.get_balance("USDT") == pytest.approx(expected_cash, abs=0.01)

    def test_sell_credits_net_of_fee(self, tmp_path):
        b = make(tmp_path)
        b.market_order("X/USDT", "buy", 10.0)
        before = b.get_balance("USDT")
        r = b.market_order("X/USDT", "sell", 10.0)
        assert r.avg_price == pytest.approx(100.0 * (1 - SLIPPAGE))
        assert b.get_balance("USDT") == pytest.approx(
            before + r.avg_price * 10 * (1 - FEE), abs=0.01)

    def test_roundtrip_costs_are_positive(self, tmp_path):
        b = make(tmp_path)
        b.market_order("X/USDT", "buy", 10.0)
        b.market_order("X/USDT", "sell", 10.0)
        assert b.get_balance("USDT") < INITIAL_CASH  # 往返必付成本


class TestGuards:
    def test_insufficient_cash_raises(self, tmp_path):
        b = make(tmp_path)
        with pytest.raises(RuntimeError):
            b.market_order("X/USDT", "buy", 1000.0)  # 10萬 > 1萬

    def test_precision_floors_not_rounds(self, tmp_path):
        b = make(tmp_path)
        assert b.amount_to_precision("X", 1.999999) == 1.99999  # 捨去,不進位

    def test_cash_persists_across_instances(self, tmp_path):
        b = make(tmp_path)
        b.market_order("X/USDT", "buy", 10.0)
        cash = b.get_balance("USDT")
        b2 = make(tmp_path)
        assert b2.get_balance("USDT") == pytest.approx(cash, abs=0.01)