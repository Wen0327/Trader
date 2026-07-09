import { useState } from "react";
import { fetchChart, fetchValueScreen, fmtTs } from "../api";
import { CandleChart } from "../components/CandleChart";
import { ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

export function ValueScreen() {
  const { data, error } = useLoad(fetchValueScreen);
  const [selected, setSelected] = useState<string | null>(null);
  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;

  const c = data.criteria;
  return (
    <>
      <h2>
        台股價值篩選
        <InfoTip text={`每週更新。門檻:殖利率 ≥ ${c.min_dividend_yield}%、營收成長 ≥ ${c.min_revenue_growth}%、獲利率 ≥ ${c.min_profit_margin}%。「產業前景」不可量化,由你定性判斷 — 此為研究工具,與趨勢系統分離`}
        />
      </h2>
      <p className="muted">
        更新:{fmtTs(data.scanned_at)}|通過 {data.rows.filter((r) => r.passed).length}
        /{data.fetched}
      </p>
      <table>
        <thead>
          <tr>
            <th></th><th>代號</th><th>名稱</th><th>股價</th>
            <th>殖利率</th><th>營收成長</th><th>獲利率</th><th>PE</th><th>負債/權益</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr
              key={r.ticker}
              className={`clickable ${r.passed ? "" : "row-dim"} ${selected === r.ticker ? "selected" : ""}`}
              onClick={() => setSelected(r.ticker)}
            >
              <td>{r.passed ? "✅" : ""}</td>
              <td>{r.ticker.replace(/\.TWO?$/, "")}</td>
              <td>{r.name}</td>
              <td>{r.price}</td>
              <td className={r.dividend_yield != null && r.dividend_yield >= c.min_dividend_yield ? "good" : "muted"}>
                {r.dividend_yield != null ? `${r.dividend_yield}%` : "—"}
              </td>
              <td className={r.revenue_growth != null && r.revenue_growth >= 0 ? "good" : "bad"}>
                {r.revenue_growth != null ? `${r.revenue_growth > 0 ? "+" : ""}${r.revenue_growth}%` : "—"}
              </td>
              <td>{r.profit_margin != null ? `${r.profit_margin}%` : "—"}</td>
              <td>{r.pe ?? "—"}</td>
              <td>{r.debt_to_equity ?? "—"}</td>
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
