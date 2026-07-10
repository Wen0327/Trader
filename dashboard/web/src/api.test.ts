/** fmtTs:API 時間戳(UTC)→ 本地時區顯示。測試固定 TZ=Asia/Taipei(+8)。 */
import { describe, expect, it } from "vitest";
import { fmtTs } from "./api";

describe("fmtTs", () => {
  it("UTC 轉 +8 本地時間", () => {
    expect(fmtTs("2026-07-10 00:30:00")).toBe("2026-07-10 08:30:00");
  });

  it("跨日進位", () => {
    expect(fmtTs("2026-07-09 20:00:00")).toBe("2026-07-10 04:00:00");
  });

  it("跨年進位", () => {
    expect(fmtTs("2025-12-31 23:00:00")).toBe("2026-01-01 07:00:00");
  });

  it("支援 ISO 格式(T 分隔)", () => {
    expect(fmtTs("2026-07-10T00:30:00Z")).toBe("2026-07-10 08:30:00");
  });

  it("null / undefined 顯示破折號", () => {
    expect(fmtTs(null)).toBe("—");
    expect(fmtTs(undefined)).toBe("—");
  });

  it("非時間字串原樣返回", () => {
    expect(fmtTs("n/a")).toBe("n/a");
  });
});
