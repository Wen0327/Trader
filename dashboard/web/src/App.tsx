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

// 開發頁(testnet 操作/回測)只在本機顯示;部署站僅保留研究頁
const DEV_TABS: readonly Tab[] = ["總覽", "交易", "回測"];
const IS_LOCAL = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const LS_DEV = "show-dev-tabs";

export default function App() {
  const [tab, setTab] = useState<Tab>("總覽");
  const [showDev, setShowDev] = useState(
    () => IS_LOCAL && localStorage.getItem(LS_DEV) !== "0",
  );
  const toggleDev = () => setShowDev((v) => {
    localStorage.setItem(LS_DEV, v ? "0" : "1");
    return !v;
  });
  // auth: null = 檢查中, "" = 未登入, 其他 = 已登入 email
  const [user, setUser] = useState<string | null>(null);

  const check = useCallback(
    () => fetchMe().then((r) => setUser(r.email)).catch(() => setUser("")),
    [],
  );
  useEffect(() => { check(); }, [check]);

  if (user === null) return <div className="login-box"><p className="muted">驗證中…</p></div>;
  if (user === "") return <Login onCheck={check} />;

  const visibleTabs = (Object.keys(TABS) as Tab[])
    .filter((t) => showDev || !DEV_TABS.includes(t));
  const active = visibleTabs.includes(tab) ? tab : visibleTabs[0];
  const Page = TABS[active];
  return (
    <div className="app">
      <header>
        <h1>Trader</h1>
        <nav>
          {visibleTabs.map((t) => (
            <button key={t} className={t === active ? "active" : ""} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </nav>
        {IS_LOCAL && (
          <label className="toggle" title="總覽/交易/回測(僅本機可切換)">
            <input type="checkbox" checked={showDev} onChange={toggleDev} />
            DEV
          </label>
        )}
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
