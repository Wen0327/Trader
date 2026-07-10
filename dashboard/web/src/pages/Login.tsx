import { useState } from "react";
import { requestLogin } from "../api";

export function Login({ onCheck }: { onCheck: () => void }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email.includes("@") || busy) return;
    setBusy(true);
    try {
      await requestLogin(email);
      setSent(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-box">
      <h1>Trader</h1>
      {sent ? (
        <>
          <p>若該 email 有權限,驗證信已寄出 — 點擊信中連結完成登入。</p>
          <p className="muted">連結 15 分鐘內有效。登入後此頁會自動更新,或
            <button className="drawer-close" onClick={onCheck}>我已點擊,重新檢查</button>
          </p>
        </>
      ) : (
        <>
          <p className="muted">輸入 email 取得登入連結</p>
          <div className="login-row">
            <input
              type="email"
              value={email}
              placeholder="you@example.com"
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
            <button className="login-btn" onClick={submit} disabled={busy}>
              {busy ? "寄送中…" : "寄送驗證信"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
