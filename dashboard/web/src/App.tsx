import { useCallback, useEffect, useState } from "react";
import { fetchMe, logout } from "./api";
import { Login } from "./pages/Login";
import { PaperBooks } from "./pages/PaperBooks";
import { TradeHistory } from "./pages/TradeHistory";
import { ValueScreen } from "./pages/ValueScreen";
import "./App.css";

const TABS = {
  台股: ValueScreen,
  帳本: PaperBooks,
  交易紀錄: TradeHistory,
} as const;
type Tab = keyof typeof TABS;

export default function App() {
  const [tab, setTab] = useState<Tab>("台股");
  // auth: null = 檢查中, "" = 未登入, 其他 = 已登入 email
  const [user, setUser] = useState<string | null>(null);

  const check = useCallback(
    () => fetchMe().then((r) => setUser(r.email)).catch(() => setUser("")),
    [],
  );
  useEffect(() => { check(); }, [check]);

  if (user === null) return <div className="login-box"><p className="muted">驗證中…</p></div>;
  if (user === "") return <Login onCheck={check} />;

  const Page = TABS[tab];
  return (
    <div className="app">
      <header>
        <h1>Trader</h1>
        <nav>
          {(Object.keys(TABS) as Tab[]).map((t) => (
            <button key={t} className={t === tab ? "active" : ""} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </nav>
        <button
          className="drawer-close"
          title={user}
          onClick={() => logout().then(() => setUser(""))}
        >
          登出
        </button>
      </header>
      <main>
        <Page />
      </main>
    </div>
  );
}
