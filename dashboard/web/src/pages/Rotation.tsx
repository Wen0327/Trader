import { useState } from "react";
import {
  Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchRotation, fetchRotationTicker } from "../api";
import { CandleChart } from "../components/CandleChart";
import { ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { StatusBadge } from "../components/StatusBadge";
import { useLoad } from "../hooks/useLoad";

export function Rotation() {
  const { data, error } = useLoad(fetchRotation);
  const [selected, setSelected] = useState<string | null>(null);

  if (error) return <ErrorBox msg={error} />;
  if (!data) return <p className="muted">載入中…(比值歷史首次載入需幾秒)</p>;

  return (
    <>
      <h2>第一幕:輪動比值 <InfoTip text="比值站上自身 200MA = 資金離開 AI 巨頭、流向廣度市場的趨勢級證據" /></h2>
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
          <tr>
            <th>狀態</th><th>標的</th><th>說明</th><th>價格</th>
            <th>200MA</th><th>距55日高</th>
            <th>距出場線 <InfoTip text="現價距 20 日低的緩衝 — 跌破即訊號失效。僅訊號有效中的標的顯示" /></th>
          </tr>
        </thead>
        <tbody>
          {data.watchlist.map((w) => (
            <tr
              key={w.ticker}
              className={`clickable ${selected === w.ticker ? "selected" : ""}`}
              onClick={() => setSelected(w.ticker)}
            >
              <td><StatusBadge item={w} /></td>
              <td>{w.ticker}</td>
              <td className="muted">{w.label}</td>
              <td>{w.price}</td>
              <td className={w.above_ma200 ? "good" : "bad"}>
                {w.above_ma200 ? "站上" : "跌破"} ({w.pct_vs_ma200 > 0 ? "+" : ""}{w.pct_vs_ma200}%)
              </td>
              <td className={w.pct_to_55d_high > -3 ? "good" : ""}>{w.pct_to_55d_high}%</td>
              <td className={w.pct_to_exit == null ? "muted" : w.pct_to_exit > 5 ? "good" : "bad"}>
                {w.pct_to_exit == null ? "—" : `+${w.pct_to_exit}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && <TickerChart ticker={selected} />}
    </>
  );
}

function TickerChart({ ticker }: { ticker: string }) {
  const { data, error, fetching } = useLoad(
    () => fetchRotationTicker(ticker), [ticker], { keepPrevious: true },
  );
  const [showBreakouts, setShowBreakouts] = useState(false);
  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;
  return (
    <>
      <h2>
        {ticker} — {data.ticker === ticker ? data.label : "載入中…"}
        <InfoTip text="兩道確認門:站上 200MA(黃線)= 有資格考慮;突破 55 日高(綠虛線)= 扣扳機,趨勢確立。綠色三角 = 歷史上收盤突破 55 日高的日子" />
        <label className="toggle">
          <input
            type="checkbox"
            checked={showBreakouts}
            onChange={(e) => setShowBreakouts(e.target.checked)}
          />
          突破標記
        </label>
      </h2>
      <div style={{ opacity: fetching ? 0.45 : 1, transition: "opacity 0.15s" }}>
        <CandleChart data={data} showBreakouts={showBreakouts} />
        <p className="muted chart-legend">
          黃線 200MA ｜ 綠虛線 55日高(進場)｜ 紅虛線 20日低(出場)｜ ▲ 歷史突破日
        </p>
      </div>
    </>
  );
}
