import {
  Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchEquity, fetchFng, fetchStatus, fmtTs } from "../api";
import { Card, Cards } from "../components/Card";
import { Empty, ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

const REFRESH = { keepPrevious: true, refreshMs: 60_000 };

export function Overview() {
  const status = useLoad(fetchStatus, [], REFRESH);
  const equity = useLoad(fetchEquity, [], REFRESH);
  const fng = useLoad(fetchFng, [], { keepPrevious: true, refreshMs: 300_000 });

  if (status.error || equity.error) return <ErrorBox msg={(status.error ?? equity.error)!} />;
  if (!status.data || !equity.data) return <Loading />;

  const s = status.data;
  const positions = Object.entries(s.positions);
  return (
    <>
      <Cards>
        <Card label="權益 (USDT)" value={s.equity?.toFixed(2) ?? "—"} />
        <Card
          label="Kill Switch"
          value={s.kill_switch == null ? "—" : s.kill_switch ? "觸發" : "正常"}
          tone={s.kill_switch ? "bad" : "good"}
        />
        <Card label="持倉數" value={String(positions.length)} />
        <Card
          label="恐懼貪婪指數"
          value={fng.data?.value != null ? `${fng.data.value} ${fng.data.label}` : "—"}
          tone={fng.data?.value != null && fng.data.value < 40 ? "bad"
            : fng.data?.value != null && fng.data.value > 60 ? "good" : undefined}
        />
        <Card label="最後更新" value={fmtTs(s.updated_at)} tone="small" />
      </Cards>

      <h2>權益曲線</h2>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={equity.data.map((p) => ({ ...p, ts: fmtTs(p.ts) }))}>
          <XAxis dataKey="ts" hide />
          <YAxis domain={["auto", "auto"]} width={70} />
          <Tooltip />
          <Line dataKey="equity" dot={false} stroke="#4f9cf9" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>

      <h2>現貨持倉</h2>
      {positions.length === 0 ? (
        <Empty msg="空手(等待 Donchian 55 日高突破訊號)" />
      ) : (
        <PositionTable rows={positions} />
      )}

      <h2>合約軌道 <InfoTip text="週期空單策略:合約 testnet 紙上驗證,槓桿 1x 硬鎖,2026-10 窗口結束覆盤" /></h2>
      <Cards>
        <Card label="合約權益 (USDT)" value={s.futures.equity?.toFixed(2) ?? "—"} />
        <Card
          label="合約 Kill Switch"
          value={s.futures.kill_switch == null ? "—" : s.futures.kill_switch ? "觸發" : "正常"}
          tone={s.futures.kill_switch ? "bad" : "good"}
        />
        <Card label="空單持倉數" value={String(Object.keys(s.futures.positions).length)} />
      </Cards>
      {Object.keys(s.futures.positions).length === 0 ? (
        <Empty msg="無空單(等待:週期窗口內 + 破55日低 + 未跌破50%地板)" />
      ) : (
        <PositionTable rows={Object.entries(s.futures.positions)} />
      )}

      <h2>紙上軌道 <InfoTip text="testnet 不支援的標的走自製撮合影子帳本。US:QQQB Regime200,幣安公開行情成交(每小時);TW:動量 TOP10 季調倉,台股費制(週估值)。持倉明細見各市場分頁" /></h2>
      <Cards>
        <Card label="紙上 US (USDT)" value={s.paper?.equity?.toFixed(2) ?? "—"} />
        <Card
          label="US 持倉數"
          value={String(Object.keys(s.paper?.positions ?? {}).length)}
        />
        <Card
          label="紙上 TW (TWD)"
          value={s.paper_tw?.equity?.toLocaleString() ?? "—"}
        />
        <Card label="TW 持倉數" value={String(s.paper_tw?.positions_count ?? 0)} />
      </Cards>
    </>
  );
}

function PositionTable({ rows }: {
  rows: [string, { amount: number; entry_price: number }][];
}) {
  return (
    <table>
      <thead><tr><th>標的</th><th>數量</th><th>進場價</th></tr></thead>
      <tbody>
        {rows.map(([sym, p]) => (
          <tr key={sym}>
            <td>{sym}</td>
            <td className={p.amount < 0 ? "bad" : ""}>{p.amount}</td>
            <td>{p.entry_price}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
