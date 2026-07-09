import { fetchScan, fmtTs } from "../api";
import { ErrorBox, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

export function Scanner() {
  const { data, error } = useLoad(fetchScan);
  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;

  return (
    <>
      <p className="muted">掃描時間:{fmtTs(data.scanned_at)} UTC</p>
      {data.crypto_sentiment && (
        <p>
          Crypto 情緒:
          {Object.entries(data.crypto_sentiment).map(([k, v]) => (
            <span key={k} className="sentiment">
              {k.split("/")[0]} {v == null ? "n/a" : v.toFixed(2)}
            </span>
          ))}
        </p>
      )}
      <table>
        <thead>
          <tr><th>#</th><th>標的</th><th>24h</th><th>量 (USDT)</th><th>情緒</th><th>頭條</th></tr>
        </thead>
        <tbody>
          {data.movers.map((m) => (
            <tr key={m.symbol}>
              <td>{m.rank}</td>
              <td>{m.symbol.split("/")[0]}</td>
              <td className={m.change_pct >= 0 ? "good" : "bad"}>
                {m.change_pct.toFixed(1)}%
              </td>
              <td>{m.quote_volume_usdt.toLocaleString()}</td>
              <td>{m.sentiment == null ? "—" : m.sentiment.toFixed(2)}</td>
              <td className="headlines">{(m.headlines ?? []).join(" / ")}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {data.rotation && (
        <>
          <h2>資金輪動監控(AI 受害者觀察清單 — 只觀察,突破才考慮)</h2>
          <p>
            {data.rotation.ratios.map((r) => (
              <span key={r.pair} className="sentiment">
                {r.pair}:{" "}
                <span className={r.rotation_on ? "good" : "muted"}>
                  {r.rotation_on ? "🟢 輪動啟動" : "⚪ 未啟動"}
                </span>{" "}
                (vs 200MA {r.pct_vs_ma200 > 0 ? "+" : ""}{r.pct_vs_ma200}%)
              </span>
            ))}
          </p>
          <table>
            <thead>
              <tr><th>標的</th><th>說明</th><th>價格</th><th>200MA</th><th>距55日高</th></tr>
            </thead>
            <tbody>
              {data.rotation.watchlist.map((w) => (
                <tr key={w.ticker}>
                  <td>{w.ticker}</td>
                  <td className="muted">{w.label}</td>
                  <td>{w.price}</td>
                  <td className={w.above_ma200 ? "good" : "bad"}>
                    {w.above_ma200 ? "站上" : "跌破"} ({w.pct_vs_ma200 > 0 ? "+" : ""}{w.pct_vs_ma200}%)
                  </td>
                  <td className={w.pct_to_55d_high > -3 ? "good" : ""}>
                    {w.pct_to_55d_high}%
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
