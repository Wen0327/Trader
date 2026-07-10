"""Magic-link 認證:email 白名單 + 一次性驗證連結 + 長效 session。

安全設計:
- 白名單外的 email 一律回覆相同訊息(不洩漏名單)
- magic token 一次性、15 分鐘效期;session 90 天、httpOnly cookie
- session 存伺服器端(storage/auth_sessions.json),可隨時撤銷
- SMTP 未設定時為開發後備:驗證連結印到 API log(僅限本機使用)
"""

from __future__ import annotations

import json
import os
import secrets
import smtplib
import time
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAGIC_TTL = 15 * 60
SESSION_TTL = 90 * 86400
COOKIE_NAME = "trader_session"


def _allowed_emails() -> set[str]:
    raw = os.environ.get("ALLOWED_EMAILS", "x36352580@gmail.com")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


class AuthStore:
    def __init__(self, pending_path: Path | None = None,
                 sessions_path: Path | None = None):
        self.pending_path = pending_path or ROOT / "storage" / "auth_pending.json"
        self.sessions_path = sessions_path or ROOT / "storage" / "auth_sessions.json"

    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text()) if path.exists() else {}

    def _save(self, path: Path, data: dict) -> None:
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data))

    # --- magic link ---
    def issue_magic(self, email: str) -> str | None:
        """白名單通過 → 回傳 token;否則 None(呼叫端回覆一律相同)。"""
        if email.strip().lower() not in _allowed_emails():
            return None
        pending = self._load(self.pending_path)
        now = time.time()
        pending = {t: v for t, v in pending.items() if v["exp"] > now}  # 清過期
        token = secrets.token_urlsafe(32)
        pending[token] = {"email": email.strip().lower(), "exp": now + MAGIC_TTL}
        self._save(self.pending_path, pending)
        return token

    def redeem_magic(self, token: str) -> str | None:
        """一次性兌換:成功回傳 email 並銷毀 token。"""
        pending = self._load(self.pending_path)
        entry = pending.pop(token, None)
        self._save(self.pending_path, pending)
        if entry and entry["exp"] > time.time():
            return entry["email"]
        return None

    # --- session ---
    def create_session(self, email: str) -> str:
        sessions = self._load(self.sessions_path)
        sid = secrets.token_urlsafe(32)
        sessions[sid] = {"email": email, "exp": time.time() + SESSION_TTL}
        self._save(self.sessions_path, sessions)
        return sid

    def get_email(self, sid: str | None) -> str | None:
        if not sid:
            return None
        entry = self._load(self.sessions_path).get(sid)
        if entry and entry["exp"] > time.time():
            return entry["email"]
        return None

    def revoke(self, sid: str | None) -> None:
        if not sid:
            return
        sessions = self._load(self.sessions_path)
        sessions.pop(sid, None)
        self._save(self.sessions_path, sessions)


def send_magic_email(email: str, link: str) -> bool:
    """寄驗證信。SMTP 未設定 → 回 False(呼叫端 fallback 印 log)。"""
    user = os.environ.get("GMAIL_USER", "").strip()
    pwd = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not user or not pwd:
        return False
    msg = MIMEText(
        f"點擊以下連結登入 Trader 儀表板(15 分鐘內有效):\n\n{link}\n\n"
        "若非本人操作請忽略此信。", "plain", "utf-8")
    msg["Subject"] = "Trader 儀表板登入連結"
    msg["From"] = user
    msg["To"] = email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
        s.login(user, pwd)
        s.sendmail(user, [email], msg.as_string())
    return True
