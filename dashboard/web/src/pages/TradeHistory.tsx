import { useState } from "react";
import type { PaperTradesReport } from "../api";
import { fetchPaperTrades } from "../api";
import { Card, Cards } from "../components/Card";
import { ErrorBox, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

export function TradeHistory() {
  const [book, setBook] = useState<"tw" | "tw_d">("tw");
  const { data, error } = useLoad(() => fetchPaperTrades(book), [book],
    { keepPrevious: true });
  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;

  const totalPnl = data.summary.total_realized_pnl + data.summary.total_unrealized_pnl;

  return (
    <>
      <div className="toolbar">
        <button className={book === "tw" ? "active" : ""} onClick={() => setBook("tw")}>
          A 標準版
        </button>
        <button className={book === "tw_d" ? "active" : ""} onClick={() => setBook("tw_d")}>
          🧪 D 恐慌部署
        </button>
      </div>
      <Cards>
        <Card
          label="未實現損益"
          value={`${data.summary.total_unrealized_pnl > 0 ? "+" : ""}${data.summary.total_unrealized_pnl.toLocaleString()}`}
          tone={data.summary.total_unrealized_pnl >= 0 ? "good" : "bad"}
        />
        <Card
          label="已實現損益"
          value={`${data.summary.total_realized_pnl > 0 ? "+" : ""}${data.summary.total_realized_pnl.toLocaleString()}`}
          tone={data.summary.total_realized_pnl >= 0 ? "good" : "bad"}
        />
        <Card
          label="合計損益"
          value={`${totalPnl > 0 ? "+" : ""}${totalPnl.toLocaleString()}`}
          tone={totalPnl >= 0 ? "good" : "bad"}
        />
        <Card label="勝率" value={`${data.summary.win_rate}%`}
          tone={data.summary.win_rate >= 50 ? "good" : "bad"} />
        <Card label="平均獲利" value={`+${data.summary.avg_win.toLocaleString()}`} tone="good" />
        <Card label="平均虧損" value={data.summary.avg_loss.toLocaleString()} tone="bad" />
      </Cards>

      <HoldingsTable holdings={data.holdings} />
      <SellsTable data={data} />
      <h2>全部紀錄</h2>
      <AllTradesTable data={data} />
    </>
  );
}

function HoldingsTable({ holdings }: { holdings: PaperTradesReport["holdings"] }) {
  if (holdings.length === 0) return null;
  return (
    <>
      <h2>持倉未實現損益</h2>
      <table>
        <thead>
          <tr>
            <th>標的</th><th>股數</th><th>成本</th><th>現價</th><th>損益 %</th><th>損益金額</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const amt = Math.round(h.shares * (h.price - h.entry_price));
            return (
              <tr key={h.ticker}>
                <td>{h.ticker.replace(/\.TWO?$/, "")} {h.name}</td>
                <td>{h.shares.toLocaleString()}</td>
                <td>{h.entry_price.toLocaleString()}</td>
                <td>{h.price.toLocaleString()}</td>
                <td className={h.pnl_pct >= 0 ? "good" : "bad"}>
                  {h.pnl_pct > 0 ? "+" : ""}{h.pnl_pct}%
                </td>
                <td className={amt >= 0 ? "good" : "bad"}>
                  {amt > 0 ? "+" : ""}{amt.toLocaleString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function SellsTable({ data }: { data: PaperTradesReport }) {
  const sells = data.trades.filter(
    (t) => t.side === "sell" && t.pnl_pct != null,
  );
  if (sells.length === 0) return null;

  return (
    <>
      <h2>已實現損益（平倉紀錄）</h2>
      <table>
        <thead>
          <tr>
            <th>日期</th><th>標的</th><th>股數</th>
            <th>買入價</th><th>賣出價</th><th>損益 %</th><th>損益金額</th>
          </tr>
        </thead>
        <tbody>
          {[...sells].reverse().map((t, i) => {
            const entry = t.price! / (1 + t.pnl_pct! / 100);
            const amt = Math.round(t.shares * t.price! - t.shares * entry);
            return (
              <tr key={i}>
                <td>{t.date}</td>
                <td>{t.ticker.replace(/\.TWO?$/, "")} {t.name ?? ""}{t.note ? ` (${t.note})` : ""}</td>
                <td>{t.shares.toLocaleString()}</td>
                <td>{Math.round(entry).toLocaleString()}</td>
                <td>{t.price!.toLocaleString()}</td>
                <td className={t.pnl_pct! >= 0 ? "good" : "bad"}>
                  {t.pnl_pct! > 0 ? "+" : ""}{t.pnl_pct}%
                </td>
                <td className={amt >= 0 ? "good" : "bad"}>
                  {amt > 0 ? "+" : ""}{amt.toLocaleString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function AllTradesTable({ data }: { data: PaperTradesReport }) {
  return (
    <table>
      <thead>
        <tr>
          <th>日期</th><th>方向</th><th>標的</th><th>股數</th>
          <th>價格</th><th>損益 %</th><th>損益金額</th>
        </tr>
      </thead>
      <tbody>
        {[...data.trades].reverse().map((t, i) => {
          const sideLabel = { buy: "買入", sell: "賣出", split: "分割" }[t.side] ?? t.side;
          const sideTone = t.side === "buy" ? "good" : t.side === "sell" ? "bad" : "";
          const amt = t.pnl_pct != null && t.price != null
            ? Math.round(t.shares * t.price * t.pnl_pct / (100 + t.pnl_pct))
            : null;
          return (
            <tr key={i}>
              <td>{t.date}</td>
              <td className={sideTone}>{sideLabel}</td>
              <td>{t.ticker.replace(/\.TWO?$/, "")} {t.name ?? ""}{t.note ? ` (${t.note})` : ""}</td>
              <td>{t.shares.toLocaleString()}</td>
              <td>{t.price ?? "—"}</td>
              <td className={t.pnl_pct == null ? "" : t.pnl_pct >= 0 ? "good" : "bad"}>
                {t.pnl_pct == null ? "—" : `${t.pnl_pct > 0 ? "+" : ""}${t.pnl_pct}%`}
              </td>
              <td className={amt == null ? "" : amt >= 0 ? "good" : "bad"}>
                {amt == null ? "—" : `${amt > 0 ? "+" : ""}${amt.toLocaleString()}`}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
