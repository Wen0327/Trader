import { useState } from "react";
import type { BrokerPendingReport, BrokerPositionsReport } from "../api";
import { fetchBrokerPending, fetchBrokerPositions, fetchBrokerStatus } from "../api";
import { Card, Cards } from "../components/Card";
import { Empty, ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

export function BrokerPage() {
  const status = useLoad(fetchBrokerStatus);
  const pending = useLoad(fetchBrokerPending, [], { keepPrevious: true, refreshMs: 60_000 });

  if (status.error) return <ErrorBox msg={status.error} />;
  if (!status.data) return <Loading />;

  const s = status.data;

  return (
    <>
      <h2>
        券商連線（永豐 Shioaji）
        <InfoTip text="按需連線：點「查詢持倉」才連券商，用完即斷。不維持長連線。" />
      </h2>
      <Cards>
        <Card label="API 設定" value={s.configured ? "已設定" : "未設定"}
          tone={s.configured ? "good" : "bad"} />
        <Card label="模式" value={s.mode === "simulation" ? "模擬盤" : "正式盤"}
          tone={s.mode === "simulation" ? undefined : "bad"} />
        <Card label="CA 憑證" value={s.has_ca ? "已設定" : "未設定（模擬不需要）"}
          tone="small" />
      </Cards>

      {pending.data && pending.data.n_total > 0 && (
        <PendingPanel data={pending.data} />
      )}

      {s.configured ? <PositionsPanel /> : (
        <Empty msg="請在 .env 設定 SJ_API_KEY 和 SJ_SECRET_KEY" />
      )}
    </>
  );
}

function PendingPanel({ data }: { data: BrokerPendingReport }) {
  return (
    <>
      <h2>
        調倉執行進度
        <InfoTip text="週掃描產生的調倉委託。executor 每 30 分鐘盤中執行，全部成交後自動清除。" />
      </h2>
      <Cards>
        <Card label="總筆數" value={String(data.n_total)} />
        <Card label="已成交" value={String(data.n_filled)} tone="good" />
        <Card label="待執行" value={String(data.n_unfilled)}
          tone={data.n_unfilled > 0 ? "bad" : "good"} />
      </Cards>
      <table>
        <thead>
          <tr><th>狀態</th><th>方向</th><th>標的</th><th>股數</th><th>價格</th><th>金額</th><th>最後下單</th></tr>
        </thead>
        <tbody>
          {data.items.map((item, i) => {
            const price = item.price ?? 0;
            const amount = Math.round(item.shares * price);
            return (
              <tr key={i}>
                <td>{item.filled ? "✅" : "⏳"}</td>
                <td className={item.side === "buy" ? "good" : "bad"}>
                  {item.side === "buy" ? "買入" : "賣出"}
                </td>
                <td>{item.ticker.replace(/\.TWO?$/, "")} {item.name}</td>
                <td>{item.shares.toLocaleString()}</td>
                <td>{price ? price.toLocaleString() : "—"}</td>
                <td>{price ? `$${amount.toLocaleString()}` : "—"}</td>
                <td className="muted">{item.last_submitted ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function PositionsPanel() {
  const [data, setData] = useState<BrokerPositionsReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchBrokerPositions();
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="toolbar" style={{ marginTop: 16 }}>
        <button onClick={fetch} disabled={loading}>
          {loading ? "連線中…" : "查詢持倉"}
        </button>
      </div>

      {error && <ErrorBox msg={error} />}

      {data && (
        <>
          <h2>券商持倉（{data.positions.length} 檔）</h2>
          {data.positions.length === 0 ? (
            <Empty msg="券商無持倉" />
          ) : (
            <table>
              <thead>
                <tr><th>代號</th><th>張數</th><th>均價</th><th>現價</th><th>損益</th></tr>
              </thead>
              <tbody>
                {data.positions.map((p) => (
                  <tr key={p.code}>
                    <td>{p.code}</td>
                    <td>{p.lots}</td>
                    <td>{p.avg_price.toLocaleString()}</td>
                    <td>{p.last_price.toLocaleString()}</td>
                    <td className={p.pnl >= 0 ? "good" : "bad"}>
                      {p.pnl > 0 ? "+" : ""}{p.pnl.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h2>
            對帳（券商 vs 紙上帳本）
            <InfoTip text="比對券商實際持倉與 tw_paper_state.json 的差異。代號自動轉換(.TW ↔ 純數字)，單位自動換算(股 ↔ 張)" />
          </h2>
          <Cards>
            <Card label="券商持倉" value={`${data.positions.length} 檔`} />
            <Card label="紙上持倉" value={`${data.paper_count} 檔`} />
            <Card label="差異數"
              value={data.diffs.length === 0 ? "0（一致）" : String(data.diffs.length)}
              tone={data.diffs.length === 0 ? "good" : "bad"} />
          </Cards>
          {data.diffs.length > 0 ? (
            <table>
              <thead><tr><th>差異</th></tr></thead>
              <tbody>
                {data.diffs.map((d, i) => (
                  <tr key={i}><td className="bad">{d}</td></tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty msg="✅ 券商與紙上帳本一致" />
          )}
        </>
      )}
    </>
  );
}
