import type { ChartInterval } from "../api";

const INTERVALS: [ChartInterval, string][] = [
  ["5m", "5分"], ["15m", "15分"], ["30m", "30分"],
  ["1h", "1時"], ["4h", "4時"], ["1d", "日"],
];

/** K 線時間框切換(抽屜表頭用)。 */
export function IntervalPicker({ value, onChange }: {
  value: ChartInterval;
  onChange: (iv: ChartInterval) => void;
}) {
  return (
    <span className="interval-picker">
      {INTERVALS.map(([iv, label]) => (
        <button
          key={iv}
          className={value === iv ? "active" : ""}
          onClick={() => onChange(iv)}
        >
          {label}
        </button>
      ))}
    </span>
  );
}
