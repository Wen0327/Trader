import { useMemo, useState } from "react";
import type { ValueRow } from "../api";
import { fetchChart, fetchUsScreen, fmtTs } from "../api";
import { CandleChart } from "../components/CandleChart";
import { ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

type SortKey = "momentum_pct" | "range_pos_20d" | "price"
  | "dividend_yield" | "revenue_growth" | "profit_margin" | "pe";

export function UsScreen() {
  const { data, error } = useLoad(fetchUsScreen);
  const [selected, setSelected] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [desc, setDesc] = useState(true);

  const rows = useMemo(() => {
    if (!data) return [];
    if (!sortKey) return data.rows; // 預設:動量遞減(伺服器排序)
    const val = (r: ValueRow) => r[sortKey] ?? -Infinity;
    return [...data.rows].sort((a, b) =>
      desc ? Number(val(b)) - Number(val(a)) : Number(val(a)) - Number(val(b)));
  }, [data, sortKey, desc]);

  const onSort = (k: SortKey) => {
    if (sortKey === k) {
      if (desc) setDesc(false);
      else { setSortKey(null); setDesc(true); }
    } else { setSortKey(k); setDesc(true); }
  };
  const arrow = (k: SortKey) => (sortKey === k ? (desc ? " ▼" : " ▲") : "");

  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;

  const s = data.spy_state;
  return (
    <>
      <h2>
        美股研究瀏覽
        <InfoTip text="精選 ~85 檔各板塊龍頭。研究工具 — 無模型選股欄:美股截面動量已回測否決(前AI時代與 SPY 平手),故只給數據不掛招牌。每週更新" />
      </h2>
      <p className="muted">更新:{fmtTs(data.scanned_at)}|{data.fetched} 檔</p>

      {s && (
        <div className="cards">
          <div className="card">
            <span className="label">SPY vs 200MA</span>
            <span className={`value ${s.regime_on ? "good" : "bad"}`}>
              {s.regime_on ? "🟢" : "🔴"} {s.pct_vs_ma200 > 0 ? "+" : ""}{s.pct_vs_ma200}%
            </span>
          </div>
          <div className="card">
            <span className="label">SPY 熱度(近12月)</span>
            <span className="value">
              {s.heat_12m_pct > 0 ? "+" : ""}{s.heat_12m_pct}%
            </span>
          </div>
        </div>
      )}

      <table>
        <thead>
          <tr>
            <th>代號</th><th>名稱</th>
            <th className="sortable" onClick={() => onSort("momentum_pct")}>動量(12-1月){arrow("momentum_pct")}</th>
            <th className="sortable" onClick={() => onSort("range_pos_20d")}>
              短線位置{arrow("range_pos_20d")} <InfoTip text="(現價−20日低)÷(20日高−20日低)。🟢 回調位 = <40% 且在自身200MA上;🔴 = >70% 貼頂。執行輔助,未驗證 alpha" />
            </th>
            <th className="sortable" onClick={() => onSort("price")}>股價{arrow("price")}</th>
            <th className="sortable" onClick={() => onSort("dividend_yield")}>殖利率{arrow("dividend_yield")}</th>
            <th className="sortable" onClick={() => onSort("revenue_growth")}>營收成長{arrow("revenue_growth")}</th>
            <th className="sortable" onClick={() => onSort("profit_margin")}>獲利率{arrow("profit_margin")}</th>
            <th className="sortable" onClick={() => onSort("pe")}>PE{arrow("pe")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.ticker}
              className={`clickable ${selected === r.ticker ? "selected" : ""}`}
              onClick={() => setSelected(r.ticker)}
            >
              <td>{r.ticker}</td>
              <td>{r.name}</td>
              <td className={r.momentum_pct != null && r.momentum_pct >= 0 ? "good" : "bad"}>
                {r.momentum_pct != null ? `${r.momentum_pct > 0 ? "+" : ""}${r.momentum_pct}%` : "—"}
              </td>
              <td>
                {r.zone ? (
                  <span className={r.zone === "pullback" ? "good" : r.zone === "high" ? "bad" : "muted"}>
                    {r.zone === "pullback" ? "🟢 回調位" : r.zone === "high" ? "🔴 短線高檔" : "⚪ 中段"}
                    {" "}{r.range_pos_20d}%
                  </span>
                ) : "—"}
              </td>
              <td>{r.price}</td>
              <td className="muted">{r.dividend_yield != null ? `${r.dividend_yield}%` : "—"}</td>
              <td className="muted">
                {r.revenue_growth != null ? `${r.revenue_growth > 0 ? "+" : ""}${r.revenue_growth}%` : "—"}
              </td>
              <td className="muted">{r.profit_margin != null ? `${r.profit_margin}%` : "—"}</td>
              <td className="muted">{r.pe ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && <div style={{ height: 360 }} />}
      {selected && (
        <UsChartDrawer ticker={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}

function UsChartDrawer({ ticker, onClose }: { ticker: string; onClose: () => void }) {
  const { data, error, fetching } = useLoad(
    () => fetchChart(ticker), [ticker], { keepPrevious: true },
  );
  return (
    <div className="chart-drawer">
      <div className="chart-drawer-head">
        <strong>
          {ticker} — {data && data.ticker === ticker ? data.label : "載入中…"}
        </strong>
        <span className="muted chart-legend" style={{ marginTop: 0 }}>
          黃 200MA ｜ 綠虛 55日高 ｜ 紅虛 20日低
        </span>
        <button className="drawer-close" onClick={onClose} aria-label="關閉">✕</button>
      </div>
      {error && <ErrorBox msg={error} />}
      {!data && !error && <Loading />}
      {data && (
        <div style={{ opacity: fetching ? 0.45 : 1, transition: "opacity 0.15s" }}>
          <CandleChart data={data} showBreakouts={false} height={280} />
        </div>
      )}
    </div>
  );
}
