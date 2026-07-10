/** 分頁可見性:開發頁(總覽/交易/回測)僅本機顯示,部署站只留研究頁。 */
import { describe, expect, it } from "vitest";
import { isLocalHost, resolveActive, visibleTabs } from "./tabs";

const ALL = ["總覽", "交易", "掃描", "輪動", "台股", "美股", "帳本", "回測"] as const;

describe("isLocalHost", () => {
  it("localhost 與 127.0.0.1 視為本機", () => {
    expect(isLocalHost("localhost")).toBe(true);
    expect(isLocalHost("127.0.0.1")).toBe(true);
  });

  it("部署網域不是本機", () => {
    expect(isLocalHost("trader.example.com")).toBe(false);
  });

  it("前綴偽裝的網域不算本機", () => {
    expect(isLocalHost("localhost.evil.com")).toBe(false);
    expect(isLocalHost("127.0.0.1.evil.com")).toBe(false);
  });
});

describe("visibleTabs", () => {
  it("showDev 開:全部分頁可見", () => {
    expect(visibleTabs(ALL, true)).toEqual([...ALL]);
  });

  it("showDev 關:隱藏 總覽/交易/回測,保留研究頁", () => {
    expect(visibleTabs(ALL, false)).toEqual(["掃描", "輪動", "台股", "美股", "帳本"]);
  });
});

describe("resolveActive", () => {
  it("目前分頁仍可見 → 維持不變", () => {
    expect(resolveActive("台股", visibleTabs(ALL, false))).toBe("台股");
  });

  it("目前分頁被隱藏 → 落到第一個可見分頁(不會 undefined 白畫面)", () => {
    expect(resolveActive("總覽", visibleTabs(ALL, false))).toBe("掃描");
    expect(resolveActive("回測", visibleTabs(ALL, false))).toBe("掃描");
  });
});
