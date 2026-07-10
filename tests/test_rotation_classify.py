"""狀態階梯 classify:五級判定的邊界。"""

from data.rotation import classify


def rank(above, vs_ma, to_hi, active=False):
    return classify(above, vs_ma, to_hi, active)["status_rank"]


class TestLadder:
    def test_signal_active_overrides_everything(self):
        # 訊號存續即最高級,連 200MA 之下也一樣(如 Unity 案例)
        assert rank(False, -8.6, -8.4, active=True) == 4

    def test_near_trigger(self):
        assert rank(True, 10.0, -2.9) == 3

    def test_gate1_passed(self):
        assert rank(True, 10.0, -10.0) == 2

    def test_near_gate1(self):
        assert rank(False, -2.9, -20.0) == 1

    def test_watching(self):
        assert rank(False, -10.0, -30.0) == 0

    def test_boundary_exactly_minus_three(self):
        # 門檻為「< -3」:恰好 -3.0 屬於「接近」
        assert rank(True, 10.0, -3.0) == 3
        assert rank(False, -3.0, -20.0) == 1