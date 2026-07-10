import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // 時區敏感測試(fmtTs)固定在台北時區,本機與 CI 結果一致
    env: { TZ: "Asia/Taipei" },
  },
});
