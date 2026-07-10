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
  const [book, setBook] = useState<"us" | "tw">("us");
  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;

  return (
    <>
      <div className="toolbar">
        <button className={book === "us" ? "active" : ""} onClick={() => setBook("us")}>
          🇺🇸 美股 — QQQB Regime200
        </button>
        <button className={book === "tw" ? "active" : ""} onClick={() => setBook("tw")}>
          🇹🇼 台股 — 動量 TOP10
        </button>
      </div>

      {book === "us" ? (
        <>
          <h2>
            紙上 US
            <InfoTip text="bot 每小時管理,按幣安公開行情成交(含手續費+滑價,無盤口深度 = 實盤上界)。全額曝險鏡像策略,供 --live 決策對帳" />
          </h2>
          <UsBook us={data.us} />
        </>
      ) : (
        <>
          <h2>
            紙上 TW
            <InfoTip text="週掃描管理,季調倉(差額交易),台股實際費制(買 0.1425%、賣 0.4425% 含稅)、整股制。逐季與回測期望對帳" />
          </h2>
          <TwBook tw={data.tw} />
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

function UsBook({ us }: { us: PaperBooksReport["us"] }) {
  const positions = Object.entries(us.positions);
  return (
    <>
      <Cards>
        <Card label="權益 (USDT)" value={us.equity?.toFixed(2) ?? "—"} />
        <Card label="持倉數" value={String(positions.length)} />
      </Cards>
      {positions.length > 0 && (
        <table>
          <thead><tr><th>標的</th><th>數量</th><th>進場價</th></tr></thead>
          <tbody>
            {positions.map(([sym, p]) => (
              <tr key={sym}><td>{sym}</td><td>{p.amount}</td><td>{p.entry_price}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      <EquityCurve points={us.equity_curve} />
      {us.trades.length > 0 && (
        <>
          <h2>近期交易</h2>
          <table>
            <thead><tr><th>時間</th><th>標的</th><th>方向</th><th>數量</th><th>價格</th><th>損益</th></tr></thead>
            <tbody>
              {[...us.trades].reverse().map((t, i) => (
                <tr key={i}>
                  <td>{fmtTs(t.ts)}</td>
                  <td>{t.symbol}</td>
                  <td className={t.side === "buy" ? "good" : "bad"}>
                    {t.side === "buy" ? "買入" : "平倉"}
                  </td>
                  <td>{t.amount}</td>
                  <td>{t.price.toLocaleString()}</td>
                  <td className={t.pnl_pct == null ? "" : t.pnl_pct >= 0 ? "good" : "bad"}>
                    {t.pnl_pct == null ? "—" : `${t.pnl_pct.toFixed(2)}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
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
            <tr><th>標的</th><th>股數</th><th>進場價</th><th>現價</th><th>損益</th></tr>
          </thead>
          <tbody>
            {s.holdings.map((h) => (
              <tr key={h.ticker}>
                <td>{h.ticker.replace(/\.TWO?$/, "")} {h.name}</td>
                <td>{h.shares.toLocaleString()}</td>
                <td>{h.entry_price}</td>
                <td>{h.price}</td>
                <td className={h.pnl_pct >= 0 ? "good" : "bad"}>
                  {h.pnl_pct > 0 ? "+" : ""}{h.pnl_pct}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <EquityCurve points={tw.equity_curve} />
      {tw.trades.length > 0 && (
        <>
          <h2>近期交易</h2>
          <table>
            <thead><tr><th>日期</th><th>標的</th><th>方向</th><th>股數</th><th>價格</th><th>損益</th></tr></thead>
            <tbody>
              {[...tw.trades].reverse().map((t, i) => (
                <tr key={i}>
                  <td>{t.date}</td>
                  <td>{t.ticker.replace(/\.TWO?$/, "")} {t.name ?? ""}</td>
                  <td className={t.side === "buy" ? "good" : "bad"}>
                    {t.side === "buy" ? "買入" : "賣出"}
                  </td>
                  <td>{t.shares.toLocaleString()}</td>
                  <td>{t.price}</td>
                  <td className={t.pnl_pct == null ? "" : t.pnl_pct >= 0 ? "good" : "bad"}>
                    {t.pnl_pct == null ? "—" : `${t.pnl_pct}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
