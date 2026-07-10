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