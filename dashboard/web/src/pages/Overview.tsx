import {
  Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchEquity, fetchStatus } from "../api";
import { Card, Cards } from "../components/Card";
import { Empty, ErrorBox, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

export function Overview() {
  const status = useLoad(fetchStatus);
  const equity = useLoad(fetchEquity);

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
        <Card label="最後更新" value={s.updated_at ?? "—"} tone="small" />
      </Cards>

      <h2>權益曲線</h2>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={equity.data}>
          <XAxis dataKey="ts" hide />
          <YAxis domain={["auto", "auto"]} width={70} />
          <Tooltip />
          <Line dataKey="equity" dot={false} stroke="#4f9cf9" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>

      <h2>持倉</h2>
      {positions.length === 0 ? (
        <Empty msg="空手(等待 Donchian 55 日高突破訊號)" />
      ) : (
        <table>
          <thead><tr><th>標的</th><th>數量</th><th>進場價</th></tr></thead>
          <tbody>
            {positions.map(([sym, p]) => (
              <tr key={sym}>
                <td>{sym}</td><td>{p.amount}</td><td>{p.entry_price}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
