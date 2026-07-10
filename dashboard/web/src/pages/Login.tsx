import { useState } from "react";
import { requestLogin } from "../api";

// 裝飾 K 線(固定形態,綠紅交錯)
const CANDLES = [
  { h: 34, o: 10, up: true }, { h: 22, o: 30, up: false },
  { h: 46, o: 18, up: true }, { h: 28, o: 40, up: true },
  { h: 38, o: 26, up: false }, { h: 54, o: 30, up: true },
  { h: 30, o: 52, up: true }, { h: 44, o: 58, up: false },
  { h: 60, o: 48, up: true }, { h: 36, o: 74, up: true },
  { h: 50, o: 66, up: true }, { h: 26, o: 90, up: false },
  { h: 64, o: 78, up: true }, { h: 40, o: 100, up: true },
];

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
    <div className="login-screen">
      <div className="login-glow" />
      <div className="login-card">
        <div className="login-candles" aria-hidden>
          {CANDLES.map((c, i) => (
            <span
              key={i}
              className={`candle ${c.up ? "up" : "down"}`}
              style={{ height: c.h, marginBottom: c.o, animationDelay: `${i * 0.12}s` }}
            />
          ))}
        </div>
        <h1 className="login-logo">
          TRADER<span className="cursor" />
        </h1>
        <p className="login-sub">QUANT TERMINAL · AUTHORIZED ACCESS ONLY</p>

        {sent ? (
          <div className="login-sent">
            <p>📡 驗證信已發射 — 點擊信中連結完成登入</p>
            <p className="muted">
              連結 15 分鐘內有效。
              <button className="link-btn" onClick={onCheck}>我已點擊,重新檢查</button>
            </p>
          </div>
        ) : (
          <div className="login-row">
            <input
              type="email"
              value={email}
              placeholder="you@example.com"
              autoFocus
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
            <button className="login-btn" onClick={submit} disabled={busy}>
              {busy ? "發射中…" : "取得登入連結 →"}
            </button>
          </div>
        )}
      </div>
      <p className="login-footer">DONCHIAN · MOMENTUM · REGIME — ALL SYSTEMS NOMINAL</p>
    </div>
  );
}
