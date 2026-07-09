import { useState } from "react";
import {
  Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchRotation, fetchRotationTicker } from "../api";
import { ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

export function Rotation() {
  const { data, error } = useLoad(fetchRotation);
  const [selected, setSelected] = useState<string | null>(null);

  if (error) return <ErrorBox msg={error} />;
  if (!data) return <p className="muted">載入中…(比值歷史首次載入需幾秒)</p>;

  return (
    <>
      <h2>第一幕:輪動比值(站上 200MA = 資金離開巨頭的趨勢級證據)</h2>
      <div className="chart-row">
        {data.ratios.map((r) => (
          <div className="chart-half" key={r.pair}>
            <p>
              {r.pair}{" "}
              <span className={r.rotation_on ? "good" : "muted"}>
                {r.rotation_on ? "🟢 輪動啟動" : "⚪ 未啟動"}
              </span>
            </p>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={r.history}>
                <XAxis dataKey="date" minTickGap={70} />
                <YAxis domain={["auto", "auto"]} width={62} />
                <Tooltip />
                <Line name="比值" dataKey="ratio" dot={false} stroke="#4f9cf9" strokeWidth={1.8} />
                <Line name="200MA" dataKey="ma200" dot={false} stroke="#f0b429" strokeWidth={1.2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>

      <h2>候選人 <InfoTip text="每日 21:00 自動更新;點任一列可展開該檔走勢圖" /></h2>
      <table>
        <thead>
          <tr><th>標的</th><th>說明</th><th>價格</th><th>200MA</th><th>距55日高</th></tr>
        </thead>
        <tbody>
          {data.watchlist.map((w) => (
            <tr
              key={w.ticker}
              className={`clickable ${selected === w.ticker ? "selected" : ""}`}
              onClick={() => setSelected(w.ticker)}
            >
              <td>{w.ticker}</td>
              <td className="muted">{w.label}</td>
              <td>{w.price}</td>
              <td className={w.above_ma200 ? "good" : "bad"}>
                {w.above_ma200 ? "站上" : "跌破"} ({w.pct_vs_ma200 > 0 ? "+" : ""}{w.pct_vs_ma200}%)
              </td>
              <td className={w.pct_to_55d_high > -3 ? "good" : ""}>{w.pct_to_55d_high}%</td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && <TickerChart ticker={selected} />}
    </>
  );
}

function TickerChart({ ticker }: { ticker: string }) {
  const { data, error } = useLoad(() => fetchRotationTicker(ticker), [ticker]);
  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;
  return (
    <>
      <h2>{data.ticker} — {data.label}</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data.series}>
          <XAxis dataKey="date" minTickGap={70} />
          <YAxis domain={["auto", "auto"]} width={62} />
          <Tooltip />
          <Legend />
          <Line name="收盤價" dataKey="close" dot={false} stroke="#4f9cf9" strokeWidth={1.8} />
          <Line name="200MA(第一道門)" dataKey="ma200" dot={false} stroke="#f0b429" strokeWidth={1.2} />
          <Line name="55日高(扣扳機線)" dataKey="hi55" dot={false} stroke="#38c172" strokeWidth={1} strokeDasharray="4 3" />
        </LineChart>
      </ResponsiveContainer>
    </>
  );
}
