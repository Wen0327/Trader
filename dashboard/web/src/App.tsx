import { useCallback, useEffect, useState } from "react";
import { fetchMe, logout } from "./api";
import { BacktestPage } from "./pages/BacktestPage";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { PaperBooks } from "./pages/PaperBooks";
import { Rotation } from "./pages/Rotation";
import { Scanner } from "./pages/Scanner";
import { Trades } from "./pages/Trades";
import { UsScreen } from "./pages/UsScreen";
import { ValueScreen } from "./pages/ValueScreen";
import "./App.css";

const TABS = {
  總覽: Overview,
  交易: Trades,
  掃描: Scanner,
  輪動: Rotation,
  台股: ValueScreen,
  美股: UsScreen,
  帳本: PaperBooks,
  回測: BacktestPage,
} as const;
type Tab = keyof typeof TABS;

export default function App() {
  const [tab, setTab] = useState<Tab>("總覽");
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
        <span className="env-badge">TESTNET</span>
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
