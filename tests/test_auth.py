"""認證核心:白名單、magic token 一次性/過期、session 生命週期。"""

import time

from dashboard.auth import AuthStore


def store(tmp_path):
    return AuthStore(pending_path=tmp_path / "p.json",
                     sessions_path=tmp_path / "s.json")


class TestWhitelist:
    def test_allowed_email_gets_token(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "me@x.com")
        assert store(tmp_path).issue_magic("me@x.com") is not None

    def test_unknown_email_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "me@x.com")
        assert store(tmp_path).issue_magic("hacker@evil.com") is None

    def test_case_insensitive(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "Me@X.com")
        assert store(tmp_path).issue_magic("ME@x.COM") is not None


class TestMagicToken:
    def test_redeem_once_only(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "me@x.com")
        s = store(tmp_path)
        token = s.issue_magic("me@x.com")
        assert s.redeem_magic(token) == "me@x.com"
        assert s.redeem_magic(token) is None  # 一次性

    def test_expired_token_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "me@x.com")
        s = store(tmp_path)
        token = s.issue_magic("me@x.com")
        import json
        pending = json.loads(s.pending_path.read_text())
        pending[token]["exp"] = time.time() - 1
        s.pending_path.write_text(json.dumps(pending))
        assert s.redeem_magic(token) is None

    def test_garbage_token_rejected(self, tmp_path):
        assert store(tmp_path).redeem_magic("not-a-token") is None


class TestSession:
    def test_roundtrip(self, tmp_path):
        s = store(tmp_path)
        sid = s.create_session("me@x.com")
        assert s.get_email(sid) == "me@x.com"

    def test_revoke(self, tmp_path):
        s = store(tmp_path)
        sid = s.create_session("me@x.com")
        s.revoke(sid)
        assert s.get_email(sid) is None

    def test_none_and_garbage_sid(self, tmp_path):
        s = store(tmp_path)
        assert s.get_email(None) is None
        assert s.get_email("nope") is None


class TestRateLimiter:
    """公網暴露後 /auth/request 的防騷擾閘門:同 IP 滑動視窗限流。"""

    def _limiter(self):
        from dashboard.auth import RateLimiter
        return RateLimiter(max_hits=3, window_sec=900)

    def test_allows_within_limit(self):
        rl = self._limiter()
        assert all(rl.allow("1.2.3.4") for _ in range(3))

    def test_blocks_over_limit(self):
        rl = self._limiter()
        for _ in range(3):
            rl.allow("1.2.3.4")
        assert rl.allow("1.2.3.4") is False

    def test_ips_isolated(self):
        rl = self._limiter()
        for _ in range(3):
            rl.allow("1.2.3.4")
        assert rl.allow("5.6.7.8") is True  # 別的 IP 不受影響

    def test_window_slides(self, monkeypatch):
        rl = self._limiter()
        now = [1000.0]
        monkeypatch.setattr("dashboard.auth.time.time", lambda: now[0])
        for _ in range(3):
            rl.allow("1.2.3.4")
        assert rl.allow("1.2.3.4") is False
        now[0] += 901  # 視窗滑過 → 解封
        assert rl.allow("1.2.3.4") is True