import { fetchTrades } from "../api";
import { Empty, ErrorBox, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

export function Trades() {
  const { data, error } = useLoad(fetchTrades);
  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;
  if (data.length === 0) return <Empty msg="尚無交易紀錄" />;

  return (
    <table>
      <thead>
        <tr><th>時間</th><th>標的</th><th>方向</th><th>數量</th><th>價格</th><th>損益</th></tr>
      </thead>
      <tbody>
        {[...data].reverse().map((t, i) => (
          <tr key={i}>
            <td>{t.ts}</td>
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
  );
}
