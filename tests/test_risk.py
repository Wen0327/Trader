"""風控:三道關卡、kill switch 觸發/重置/持久化。"""

from datetime import date

import pytest

from risk.manager import RiskConfig, RiskManager, RiskViolation


def make_manager(**kw) -> RiskManager:
    return RiskManager(RiskConfig(**kw))


class TestOrderLimits:
    def test_order_within_limit_passes(self):
        make_manager().check_order(
            side="buy", order_value=999, current_position_value=0, equity=10_000)

    def test_order_over_10pct_rejected(self):
        with pytest.raises(RiskViolation):
            make_manager().check_order(
                side="buy", order_value=1_001, current_position_value=0, equity=10_000)

    def test_position_cap_30pct_rejected(self):
        with pytest.raises(RiskViolation):
            make_manager().check_order(
                side="buy", order_value=500,
                current_position_value=2_600, equity=10_000)  # 會達 31%

    def test_sell_ignores_position_cap(self):
        make_manager().check_order(
            side="sell", order_value=500,
            current_position_value=9_000, equity=10_000)


class TestKillSwitch:
    def test_triggers_on_daily_drawdown(self):
        risk = make_manager()
        risk.update_equity(10_000)
        risk.update_equity(9_400)  # -6% > 5% 閾值
        assert risk.kill_switch_active

    def test_blocks_buy_but_allows_sell(self):
        risk = make_manager()
        risk.update_equity(10_000)
        risk.update_equity(9_400)
        with pytest.raises(RiskViolation):
            risk.check_order(side="buy", order_value=100,
                             current_position_value=0, equity=9_400)
        risk.check_order(side="sell", order_value=100,
                         current_position_value=500, equity=9_400)  # 逃生門常開

    def test_small_drawdown_does_not_trigger(self):
        risk = make_manager()
        risk.update_equity(10_000)
        risk.update_equity(9_600)  # -4% < 5%
        assert not risk.kill_switch_active

    def test_state_roundtrip_preserves_kill(self):
        risk = make_manager()
        risk.update_equity(10_000)
        risk.update_equity(9_000)
        state = risk.to_dict()

        restored = make_manager()
        restored.restore(state)
        assert restored.kill_switch_active  # 重啟不能洗掉熔斷

    def test_new_day_resets(self):
        risk = make_manager()
        risk.restore({"day": "2020-01-01", "day_start_equity": 10_000, "killed": True})
        risk.update_equity(9_999)  # 今天 ≠ 2020-01-01 → 重置
        assert not risk.kill_switch_active
        assert risk.to_dict()["day"] == date.today().isoformat()
