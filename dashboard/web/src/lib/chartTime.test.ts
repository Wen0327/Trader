/** K 線時間軸:日線傳 "YYYY-MM-DD" 字串;分鐘級傳 UTC "YYYY-MM-DD HH:MM",
 *  需轉 epoch 秒並平移到觀看者時區(lightweight-charts 以 UTC 顯示數字時間)。 */
import { describe, expect, it } from "vitest";
import { toChartTime } from "./chartTime";

describe("toChartTime", () => {
  it("日線字串原樣通過", () => {
    expect(toChartTime("2026-07-13", -480)).toBe("2026-07-13");
  });

  it("分鐘級:UTC 轉 epoch 並平移到台北時區(+8)", () => {
    // 2026-07-13 05:20 UTC = epoch 1783574400 + 19200 = 1784006400?
    // 直接驗證關係式:結果 = 真實 epoch − tzOffsetMin×60
    const utcEpoch = Date.UTC(2026, 6, 13, 5, 20) / 1000;
    expect(toChartTime("2026-07-13 05:20", -480)).toBe(utcEpoch + 480 * 60);
  });

  it("UTC 觀看者(offset 0)不平移", () => {
    const utcEpoch = Date.UTC(2026, 6, 13, 5, 20) / 1000;
    expect(toChartTime("2026-07-13 05:20", 0)).toBe(utcEpoch);
  });

  it("西半球觀看者(offset 正值)往回平移", () => {
    const utcEpoch = Date.UTC(2026, 6, 13, 5, 20) / 1000;
    expect(toChartTime("2026-07-13 05:20", 300)).toBe(utcEpoch - 300 * 60); // UTC-5
  });
});
