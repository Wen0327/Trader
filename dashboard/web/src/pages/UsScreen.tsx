import { useEffect, useMemo, useState } from "react";
import type { Quotes, ValueRow } from "../api";
import { fetchChart, fetchQuotes, fetchUsScreen, fmtTs } from "../api";
import { CandleChart } from "../components/CandleChart";
import { ErrorBox, InfoTip, Loading } from "../components/Feedback";
import { useLoad } from "../hooks/useLoad";

type SortKey = "momentum_pct" | "range_pos_20d" | "price"
  | "dividend_yield" | "revenue_growth" | "profit_margin" | "pe";

/** 欄位定義:key 用於顯示偏好與排序,render 產生儲存格 */
type Col = {
  key: string;
  label: string;
  sort?: SortKey;
  tip?: string;
  render: (r: ValueRow, live: Quotes | null) => React.ReactNode;
};

const COLS: Col[] = [
  { key: "sector", label: "類別",
    render: (r) => <span className="muted">{r.sector ?? "—"}</span> },
  { key: "momentum", label: "動量(12-1月)", sort: "momentum_pct",
    render: (r) => (
      <span className={r.momentum_pct != null && r.momentum_pct >= 0 ? "good" : "bad"}>
        {r.momentum_pct != null ? `${r.momentum_pct > 0 ? "+" : ""}${r.momentum_pct}%` : "—"}
      </span>
    ) },
  { key: "zone", label: "短線位置", sort: "range_pos_20d",
    tip: "(現價−20日低)÷(20日高−20日低)。🟢 回調位 = <40% 且在自身200MA上;🔴 = >70% 貼頂。執行輔助,未驗證 alpha",
    render: (r) => r.zone ? (
      <span className={r.zone === "pullback" ? "good" : r.zone === "high" ? "bad" : "muted"}>
        {r.zone === "pullback" ? "🟢 回調位" : r.zone === "high" ? "🔴 短線高檔" : "⚪ 中段"}
        {" "}{r.range_pos_20d}%
      </span>
    ) : "—" },
  { key: "price", label: "股價", sort: "price",
    tip: "即時報價(Yahoo,約 15 分鐘延遲),每 60 秒更新;抓不到時退回週掃快照",
    render: (r, live) => live?.quotes[r.ticker]?.price ?? r.price },
  { key: "today", label: "今日",
    render: (r, live) => {
      const q = live?.quotes[r.ticker];
      if (!q) return "—";
      return (
        <span className={q.today_pct >= 0 ? "good" : "bad"}>
          {q.today_pct > 0 ? "+" : ""}{q.today_pct}%
        </span>
      );
    } },
  { key: "dy", label: "殖利率", sort: "dividend_yield",
    render: (r) => <span className="muted">{r.dividend_yield != null ? `${r.dividend_yield}%` : "—"}</span> },
  { key: "rg", label: "營收成長", sort: "revenue_growth",
    render: (r) => <span className="muted">
      {r.revenue_growth != null ? `${r.revenue_growth > 0 ? "+" : ""}${r.revenue_growth}%` : "—"}
    </span> },
  { key: "pm", label: "獲利率", sort: "profit_margin",
    render: (r) => <span className="muted">{r.profit_margin != null ? `${r.profit_margin}%` : "—"}</span> },
  { key: "pe", label: "PE", sort: "pe",
    render: (r) => <span className="muted">{r.pe ?? "—"}</span> },
];

const SECTORS = ["巨頭", "半導體", "軟體", "金融", "醫療", "消費",
                 "工業", "國防", "能源", "太空", "稀土", "其他"];
const LS_KEY = "us-screen-sectors-v2"; // 版本升級:新板塊預設全勾
const LS_STAR = "us-screen-starred";

export function UsScreen() {
  const { data, error } = useLoad(fetchUsScreen);
  const live = useLoad(() => fetchQuotes("us"), [],
    { keepPrevious: true, refreshMs: 60_000 });
  const [selected, setSelected] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [desc, setDesc] = useState(true);
  const [tier, setTier] = useState<1 | 2 | 0 | "star">(1); // 0 = 全部
  const [starred, setStarred] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(LS_STAR);
      if (saved) return new Set(JSON.parse(saved));
    } catch { /* 忽略 */ }
    return new Set();
  });

  useEffect(() => {
    localStorage.setItem(LS_STAR, JSON.stringify([...starred]));
  }, [starred]);

  const toggleStar = (t: string) => {
    setStarred((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };
  const [sectors, setSectors] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(LS_KEY);
      if (saved) return new Set(JSON.parse(saved));
    } catch { /* 忽略,回預設 */ }
    return new Set(SECTORS);
  });

  useEffect(() => {
    localStorage.setItem(LS_KEY, JSON.stringify([...sectors]));
  }, [sectors]);

  const toggleSector = (s: string) => {
    setSectors((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s);
      else next.add(s);
      return next;
    });
  };

  const shown = COLS;

  const rows = useMemo(() => {
    if (!data) return [];
    let filtered: ValueRow[];
    if (tier === "star") {
      filtered = data.rows.filter((r) => starred.has(r.ticker)); // 精選不受板塊篩選限制
    } else {
      filtered = tier === 0
        ? data.rows
        : data.rows.filter((r) => (r.tier ?? 1) === tier);
      filtered = filtered.filter((r) => sectors.has(r.sector ?? "其他"));
    }
    if (!sortKey) return filtered;
    const val = (r: ValueRow) => r[sortKey] ?? -Infinity;
    return [...filtered].sort((a, b) =>
      desc ? Number(val(b)) - Number(val(a)) : Number(val(a)) - Number(val(b)));
  }, [data, sortKey, desc, tier, sectors, starred]);

  const onSort = (k: SortKey) => {
    if (sortKey === k) {
      if (desc) setDesc(false);
      else { setSortKey(null); setDesc(true); }
    } else { setSortKey(k); setDesc(true); }
  };
  const arrow = (k?: SortKey) => (k && sortKey === k ? (desc ? " ▼" : " ▲") : "");

  if (error) return <ErrorBox msg={error} />;
  if (!data) return <Loading />;

  const s = data.spy_state;
  return (
    <>
      <h2>
        美股研究瀏覽
        <InfoTip text="精選各板塊龍頭 + 熱門題材(太空/能源)。研究工具 — 無模型選股欄:美股截面動量已回測否決,只給數據不掛招牌。財報週更、報價即時" />
      </h2>

      {s && (
        <div className="cards">
          <div className="card">
            <span className="label">SPY vs 200MA</span>
            <span className={`value ${s.regime_on ? "good" : "bad"}`}>
              {s.regime_on ? "🟢" : "🔴"} {s.pct_vs_ma200 > 0 ? "+" : ""}{s.pct_vs_ma200}%
            </span>
          </div>
          <div className="card">
            <span className="label">SPY 熱度(近12月)</span>
            <span className="value">{s.heat_12m_pct > 0 ? "+" : ""}{s.heat_12m_pct}%</span>
          </div>
        </div>
      )}

      <div className="toolbar">
        {([[1, "T1 精華"], [2, "T2 二線"], [0, "全部"],
           ["star", `⭐ 精選(${starred.size})`]] as const).map(([v, label]) => (
          <button key={String(v)} className={tier === v ? "active" : ""} onClick={() => setTier(v)}>
            {label}
          </button>
        ))}
        <span className="muted">
          更新:{fmtTs(data.scanned_at)}|顯示 {rows.length}/{data.fetched} 檔
        </span>
      </div>

      <div className="col-picker">
        <span className="muted">類別:</span>
        {SECTORS.map((s) => (
          <label key={s} className="toggle">
            <input
              type="checkbox"
              checked={sectors.has(s)}
              onChange={() => toggleSector(s)}
            />
            {s}
          </label>
        ))}
        <button
          className="drawer-close"
          onClick={() => setSectors(
            sectors.size === SECTORS.length ? new Set() : new Set(SECTORS))}
        >
          {sectors.size === SECTORS.length ? "全不選" : "全選"}
        </button>
      </div>

      <table>
        <thead>
          <tr>
            <th></th><th>代號</th><th>名稱</th>
            {shown.map((c) => (
              <th
                key={c.key}
                className={c.sort ? "sortable" : ""}
                onClick={c.sort ? () => onSort(c.sort!) : undefined}
              >
                {c.label}{arrow(c.sort)}
                {c.tip && <> <InfoTip text={c.tip} /></>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.ticker}
              className={`clickable ${selected === r.ticker ? "selected" : ""}`}
              onClick={() => setSelected(r.ticker)}
            >
              <td
                className="star-cell"
                onClick={(e) => { e.stopPropagation(); toggleStar(r.ticker); }}
                title={starred.has(r.ticker) ? "移出精選" : "加入精選"}
              >
                {starred.has(r.ticker) ? "⭐" : "☆"}
              </td>
              <td>{r.ticker}</td>
              <td>{r.name}</td>
              {shown.map((c) => (
                <td key={c.key}>{c.render(r, live.data)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {selected && <div style={{ height: 360 }} />}
      {selected && (
        <UsChartDrawer ticker={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}

function UsChartDrawer({ ticker, onClose }: { ticker: string; onClose: () => void }) {
  const { data, error, fetching } = useLoad(
    () => fetchChart(ticker), [ticker], { keepPrevious: true },
  );
  return (
    <div className="chart-drawer">
      <div className="chart-drawer-head">
        <strong>
          {ticker} — {data && data.ticker === ticker ? data.label : "載入中…"}
        </strong>
        <span className="muted chart-legend" style={{ marginTop: 0 }}>
          黃 200MA ｜ 綠虛 55日高 ｜ 紅虛 20日低
        </span>
        <button className="drawer-close" onClick={onClose} aria-label="關閉">✕</button>
      </div>
      {error && <ErrorBox msg={error} />}
      {!data && !error && <Loading />}
      {data && (
        <div style={{ opacity: fetching ? 0.45 : 1, transition: "opacity 0.15s" }}>
          <CandleChart data={data} showBreakouts={false} height={280} />
        </div>
      )}
    </div>
  );
}
