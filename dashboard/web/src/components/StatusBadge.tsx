import type { WatchItem } from "../api";

/** 候選人狀態徽章:兩道門的進度 + 近期曾突破的回落註記。 */
export function StatusBadge({ item }: { item: WatchItem }) {
  const status = item.status ?? "watching";
  const label = item.status_label ?? "⚪ 觀察中";
  const retreated =
    (item.status_rank ?? 0) < 4 && item.days_since_trigger != null;
  const gradeClass = item.signal_grade ? ` badge-grade-${item.signal_grade}` : "";
  return (
    <span className="status-cell">
      <span
        className={`badge badge-main badge-${status}${gradeClass}`}
        title={item.entry_date
          ? `${item.entry_date} 突破進場,至今 ${item.since_entry_pct}%,距出場線 ${item.pct_to_exit}%`
          : undefined}
      >
        {label}
      </span>
      {retreated && (
        <span
          className="badge badge-retreat"
          title={`${item.last_trigger_date} 曾突破 55 日高,之後跌破 20 日低,訊號已失效`}
        >
          🔄 {item.days_since_trigger}天前曾突破
        </span>
      )}
    </span>
  );
}
