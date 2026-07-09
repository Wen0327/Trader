import type { WatchItem } from "../api";

/** 候選人狀態徽章:兩道門的進度 + 近期曾突破的回落註記。 */
export function StatusBadge({ item }: { item: WatchItem }) {
  const status = item.status ?? "watching";
  const label = item.status_label ?? "⚪ 觀察中";
  const retreated =
    (item.status_rank ?? 0) < 4 && item.days_since_trigger != null;
  return (
    <>
      <span className={`badge badge-${status}`}>{label}</span>
      {retreated && (
        <span
          className="badge badge-retreat"
          title={`${item.last_trigger_date} 曾收盤突破 55 日高,之後回落`}
        >
          🔄 {item.days_since_trigger}天前曾突破
        </span>
      )}
    </>
  );
}
