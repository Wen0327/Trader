import type { WatchItem } from "../api";

/** 候選人狀態徽章:兩道門的進度視覺化。 */
export function StatusBadge({ item }: { item: WatchItem }) {
  const status = item.status ?? "watching";
  const label = item.status_label ?? "⚪ 觀察中";
  return <span className={`badge badge-${status}`}>{label}</span>;
}
