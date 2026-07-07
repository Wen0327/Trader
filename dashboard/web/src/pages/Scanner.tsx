import { fetchScan } from "../api";
import { ErrorBox, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

export function Scanner() {
  const { data, error } = useLoad(fetchScan);
  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;

  return (
    <>
      <p className="muted">掃描時間:{data.scanned_at}</p>
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
    </>
  );
}
