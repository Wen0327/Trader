import { useState } from "react";
import {
  Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchBacktest } from "../api";
import { Card, Cards } from "../components/Card";
import { ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

const SYMBOLS = ["BTC/USDT", "ETH/USDT"];
const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

export function BacktestPage() {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const { data, error } = useLoad(() => fetchBacktest(symbol), [symbol]);

  return (
    <>
      <div className="toolbar">
        {SYMBOLS.map((s) => (
          <button key={s} className={s === symbol ? "active" : ""} onClick={() => setSymbol(s)}>
            {s.split("/")[0]}
          </button>
        ))}
        <span className="muted">
          Donchian 55/20 vs Buy & Hold
          <InfoTip text="回測區間 2017-09 至今;含手續費 0.1% + 滑價 0.05%;訊號延遲一根 K 線避免前視偏差" />
        </span>
      </div>
      {error && <ErrorBox msg={error} />}
      {!data && !error && <Loading />}
      {data && (
        <>
          <Cards>
            <Card label="策略 CAGR" value={pct(data.metrics.cagr)} />
            <Card label="B&H CAGR" value={pct(data.metrics.bh_cagr)} />
            <Card label="策略 MaxDD" value={pct(data.metrics.max_drawdown)} />
            <Card label="B&H MaxDD" value={pct(data.metrics.bh_max_drawdown)} />
            <Card label="策略 Sharpe" value={data.metrics.sharpe.toFixed(2)} />
            <Card label="交易次數" value={String(data.n_trades)} />
          </Cards>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={data.curve}>
              <XAxis dataKey="date" minTickGap={60} />
              <YAxis scale="log" domain={["auto", "auto"]} width={70} />
              <Tooltip />
              <Legend />
              <Line name="Donchian 55/20" dataKey="strategy" dot={false} stroke="#4f9cf9" strokeWidth={2} />
              <Line name="Buy & Hold" dataKey="benchmark" dot={false} stroke="#888" strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </>
  );
}
