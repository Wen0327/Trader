import { useState } from "react";
import {
  Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { PaperBooksReport } from "../api";
import { fetchPaperBooks, fmtTs } from "../api";
import { Card, Cards } from "../components/Card";
import { Empty, ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

export function PaperBooks() {
  const { data, error } = useLoad(fetchPaperBooks, [],
    { keepPrevious: true, refreshMs: 60_000 });
  const [book, setBook] = useState<"tw" | "tw_d">("tw");
  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;

  return (
    <>
      <div className="toolbar">
        <button className={book === "tw" ? "active" : ""} onClick={() => setBook("tw")}>
          🇹🇼 動量 TOP10
        </button>
        <button className={book === "tw_d" ? "active" : ""} onClick={() => setBook("tw_d")}>
          🧪 TW D版(恐慌部署)
        </button>
      </div>

      {book === "tw" && (
        <>
          <h2>
            紙上 TW(A 標準版)
            <InfoTip text="週掃描管理,季調倉(差額交易),台股實際費制(買 0.1425%、賣 0.4425% 含稅)、整股制。逐季與回測期望對帳" />
          </h2>
          <TwBook tw={data.tw} />
        </>
      )}
      {book === "tw_d" && (
        <>
          <h2>
            🧪 紙上 TW(D 恐慌部署版)
            <InfoTip text="實驗帳:A 版 + 破200MA騰25%預備金、52週回撤-20%時恐慌部署。回測 Sharpe 1.30 vs A 1.26,但僅 ~4 次熊市事件 → 前瞻驗證中,下一次熊市是期末考。與 A 帳平行對照" />
          </h2>
          {data.tw_d.summary && (
            <Cards>
              <Card label="預備金 (TWD)"
                value={(data.tw_d.summary.reserve_cash ?? 0).toLocaleString()} />
              <Card label="狀態機"
                value={{ normal: "正常", reserved: "已騰預備金", deployed: "已部署" }[
                  data.tw_d.summary.exp_state ?? "normal"] ?? "—"} />
            </Cards>
          )}
          <TwBook tw={data.tw_d} />
        </>
      )}
    </>
  );
}

function EquityCurve({ points }: { points: { ts: string; equity: number }[] }) {
  if (points.length < 2) return <Empty msg="權益曲線累積中(至少需兩個紀錄點)" />;
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={points.map((p) => ({ ...p, ts: fmtTs(p.ts) }))}>
        <XAxis dataKey="ts" hide />
        <YAxis domain={["auto", "auto"]} width={80} />
        <Tooltip />
        <Line dataKey="equity" dot={false} stroke="#4f9cf9" strokeWidth={2}
              isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function TwBook({ tw }: { tw: PaperBooksReport["tw"] }) {
  const s = tw.summary;
  if (!s) return <Empty msg="台股帳本尚未開帳(等待首次週掃描)" />;
  return (
    <>
      <Cards>
        <Card label="權益 (TWD)" value={s.equity.toLocaleString()} />
        <Card
          label={`累積報酬(自 ${s.started ?? "—"})`}
          value={`${s.return_pct > 0 ? "+" : ""}${s.return_pct}%`}
          tone={s.return_pct >= 0 ? "good" : "bad"}
        />
        <Card label="現金" value={s.cash.toLocaleString()} />
        <Card label="累積交易" value={String(s.n_trades)} />
      </Cards>
      {s.holdings.length > 0 && (
        <table>
          <thead>
            <tr><th>標的</th><th>股數</th><th>進場價</th><th>現價</th><th>損益</th><th>金額</th></tr>
          </thead>
          <tbody>
            {s.holdings.map((h) => {
              const pnlAmt = Math.round(h.shares * (h.price - h.entry_price));
              return (
                <tr key={h.ticker}>
                  <td>{h.ticker.replace(/\.TWO?$/, "")} {h.name}</td>
                  <td>{h.shares.toLocaleString()}</td>
                  <td>{h.entry_price}</td>
                  <td>{h.price}</td>
                  <td className={h.pnl_pct >= 0 ? "good" : "bad"}>
                    {h.pnl_pct > 0 ? "+" : ""}{h.pnl_pct}%
                  </td>
                  <td className={pnlAmt >= 0 ? "good" : "bad"}>
                    {pnlAmt > 0 ? "+" : ""}{pnlAmt.toLocaleString()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <EquityCurve points={tw.equity_curve} />
      {tw.trades.length > 0 && (
        <>
          <h2>近期交易</h2>
          <table>
            <thead><tr><th>日期</th><th>標的</th><th>方向</th><th>股數</th><th>價格</th><th>損益</th><th>金額</th></tr></thead>
            <tbody>
              {[...tw.trades].reverse().map((t, i) => {
                const sideLabel = { buy: "買入", sell: "賣出", split: "分割" }[t.side] ?? t.side;
                const sideTone = t.side === "buy" ? "good" : t.side === "sell" ? "bad" : "";
                const pnlAmt = t.pnl_pct != null
                  ? Math.round(t.shares * t.price * t.pnl_pct / (100 + t.pnl_pct))
                  : null;
                return (
                  <tr key={i}>
                    <td>{t.date}</td>
                    <td>{t.ticker.replace(/\.TWO?$/, "")} {t.name ?? ""}{t.note ? ` (${t.note})` : ""}</td>
                    <td className={sideTone}>{sideLabel}</td>
                    <td>{t.shares.toLocaleString()}</td>
                    <td>{t.price ?? "—"}</td>
                    <td className={t.pnl_pct == null ? "" : t.pnl_pct >= 0 ? "good" : "bad"}>
                      {t.pnl_pct == null ? "—" : `${t.pnl_pct}%`}
                    </td>
                    <td className={pnlAmt == null ? "" : pnlAmt >= 0 ? "good" : "bad"}>
                      {pnlAmt == null ? "—" : `${pnlAmt > 0 ? "+" : ""}${pnlAmt.toLocaleString()}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
