/** 分頁可見性規則:開發頁(testnet 操作/回測)只在本機顯示。 */

export const DEV_TABS: readonly string[] = ["總覽", "交易", "回測"];

export const isLocalHost = (hostname: string): boolean =>
  hostname === "localhost" || hostname === "127.0.0.1";

export const visibleTabs = <T extends string>(
  all: readonly T[], showDev: boolean,
): T[] => all.filter((t) => showDev || !DEV_TABS.includes(t));

/** 目前分頁被隱藏時,退回第一個可見分頁,避免 undefined 白畫面。 */
export const resolveActive = <T extends string>(
  tab: T, visible: readonly T[],
): T => (visible.includes(tab) ? tab : visible[0]);
