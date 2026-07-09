import { useState } from "react";
import { BacktestPage } from "./pages/BacktestPage";
import { Overview } from "./pages/Overview";
import { Rotation } from "./pages/Rotation";
import { Scanner } from "./pages/Scanner";
import { Trades } from "./pages/Trades";
import { ValueScreen } from "./pages/ValueScreen";
import "./App.css";

const TABS = {
  總覽: Overview,
  交易: Trades,
  掃描: Scanner,
  輪動: Rotation,
  台股: ValueScreen,
  回測: BacktestPage,
} as const;
type Tab = keyof typeof TABS;

export default function App() {
  const [tab, setTab] = useState<Tab>("總覽");
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
      </header>
      <main>
        <Page />
      </main>
    </div>
  );
}
