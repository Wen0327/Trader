import { useMemo, useState } from "react";
import type { ValueRow } from "../api";
import { fetchChart, fetchValueScreen, fmtTs } from "../api";
import { CandleChart } from "../components/CandleChart";
import { ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

type SortKey = "momentum_pct" | "range_pos_20d" | "price"
  | "dividend_yield" | "revenue_growth" | "profit_margin" | "pe";

export function ValueScreen() {
  const { data, error } = useLoad(fetchValueScreen);
  const [selected, setSelected] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [desc, setDesc] = useState(true);

  const rows = useMemo(() => {
    if (!data) return [];
    if (!sortKey) return data.rows; // 預設:✅ 在前、動量遞減(伺服器排序)
    const val = (r: ValueRow) => r[sortKey] ?? -Infinity;
    return [...data.rows].sort((a, b) =>
      desc ? Number(val(b)) - Number(val(a)) : Number(val(a)) - Number(val(b)));
  }, [data, sortKey, desc]);

  const onSort = (k: SortKey) => {
    if (sortKey === k) {
      if (desc) setDesc(false);
      else { setSortKey(null); setDesc(true); }  // 第三次點擊回預設
    } else { setSortKey(k); setDesc(true); }
  };
  const arrow = (k: SortKey) =>
    sortKey === k ? (desc ? " ▼" : " ▲") : "";

  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;

  return (
    <>
      <h2>
        台股動量模型
        <InfoTip text="✅ = 12-1月截面動量 TOP10,剔除動量>150% 的極端拋物線(防動量崩潰,回測回撤 -40.6%→-37.7%、Sharpe 1.22→1.28)。季調倉,前瞻追蹤中逐季對帳。財報欄位為參考資訊,不參與選股" />
      </h2>
      <p className="muted">
        更新:{fmtTs(data.scanned_at)}|通過 {data.rows.filter((r) => r.passed).length}
        /{data.fetched}
      </p>

      {data.market_state && <EntryHint s={data.market_state} />}

      {data.momentum?.performance && data.momentum.performance.n_rebalances > 1 && (
        <p className="muted">
          前瞻績效(自 {data.momentum.performance.since},
          {data.momentum.performance.n_rebalances} 次調倉):
          策略 <strong>{data.momentum.performance.strategy_pct}%</strong> vs
          0050 <strong>{data.momentum.performance.bench_0050_pct}%</strong>
        </p>
      )}
      <table>
        <thead>
          <tr>
            <th></th><th>代號</th><th>名稱</th>
            <th className="sortable" onClick={() => onSort("momentum_pct")}>動量(12-1月){arrow("momentum_pct")}</th>
            <th className="sortable" onClick={() => onSort("range_pos_20d")}>
              短線位置{arrow("range_pos_20d")} <InfoTip text="(現價−20日低)÷(20日高−20日低)。🟢 回調位 = <40% 且在自身200MA上,分批進場友善;🔴 短線高檔 = >70% 貼頂。執行輔助標示,未驗證 alpha,不影響模型選股" />
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
              className={`clickable ${r.picked ? "" : "row-dim"} ${selected === r.ticker ? "selected" : ""}`}
              onClick={() => setSelected(r.ticker)}
            >
              <td>{r.picked ? "✅" : ""}</td>
              <td>{r.ticker.replace(/\.TWO?$/, "")}</td>
              <td>{r.name}</td>
              <td className={r.momentum_pct != null && r.momentum_pct >= 0 ? "good" : "bad"}>
                {r.momentum_pct != null ? `${r.momentum_pct > 0 ? "+" : ""}${r.momentum_pct}%` : "—"}
              </td>
              <td>
                {r.zone ? (
                  <span className={
                    r.zone === "pullback" ? "good" : r.zone === "high" ? "bad" : "muted"
                  }>
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

      {/* 抽屜開啟時墊高頁尾,避免表格末列被蓋住 */}
      {selected && <div style={{ height: 360 }} />}
      {selected && (
        <TwChartDrawer ticker={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}

function EntryHint({ s }: { s: NonNullable<import("../api").ValueScreenReport["market_state"]> }) {
  const win = s.bucket_win_rate;
  const [tone, verdict] =
    win >= 70 ? ["good", "歷史同狀態適合進場"] :
    win >= 55 ? ["", "歷史同狀態中性,分批為宜"] :
    ["bad", "歷史同狀態勝率偏低,謹慎"];
  return (
    <div className="cards">
      <div className="card">
        <span className="label">0050 vs 200MA</span>
        <span className={`value ${s.regime_on ? "good" : "bad"}`}>
          {s.regime_on ? "🟢" : "🔴"} {s.pct_vs_ma200 > 0 ? "+" : ""}{s.pct_vs_ma200}%
        </span>
      </div>
      <div className="card">
        <span className="label">市場熱度(近12月)</span>
        <span className="value">{s.heat_12m_pct > 0 ? "+" : ""}{s.heat_12m_pct}%({s.bucket})</span>
      </div>
      <div className="card">
        <span className="label">
          進場提示
          <InfoTip text={`依 2010-2026 回測條件分桶:目前狀態(${s.bucket})歷史下一季平均 ${s.bucket_next_q_avg > 0 ? "+" : ""}${s.bucket_next_q_avg}%、勝率 ${s.bucket_win_rate}%;200MA regime 勝率 ${s.regime_win_rate}%。樣本每桶約 16 次,參考用非保證`} />
        </span>
        <span className={`value ${tone}`}>{verdict}(勝率 {win}%)</span>
      </div>
    </div>
  );
}

function TwChartDrawer({ ticker, onClose }: { ticker: string; onClose: () => void }) {
  const { data, error, fetching } = useLoad(
    () => fetchChart(ticker), [ticker], { keepPrevious: true },
  );
  return (
    <div className="chart-drawer">
      <div className="chart-drawer-head">
        <strong>
          {ticker.replace(/\.TWO?$/, "")} —{" "}
          {data && data.ticker === ticker ? data.label : "載入中…"}
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
