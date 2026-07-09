import { useEffect, useState } from "react";

type Options = {
  /** deps 變更時保留舊資料直到新資料抵達(stale-while-revalidate),
   *  避免圖表卸載重掛造成閃爍。 */
  keepPrevious?: boolean;
  /** 自動刷新間隔(毫秒)。刷新時沿用 keepPrevious 行為,不清空畫面。 */
  refreshMs?: number;
};

/** 通用資料載入 hook:載入中 / 錯誤 / 資料三態 + 換頁重取 + 定時刷新。 */
export function useLoad<T>(
  loader: () => Promise<T>,
  deps: unknown[] = [],
  opts: Options = {},
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    let cancelled = false; // 快速連點/卸載時丟棄過期回應,避免競態

    const run = (initial: boolean) => {
      if (initial && !opts.keepPrevious) setData(null);
      if (initial) setError(null);
      setFetching(true);
      loader()
        .then((d) => { if (!cancelled) { setData(d); setError(null); } })
        .catch((e) => { if (!cancelled && initial) setError(String(e)); })
        .finally(() => { if (!cancelled) setFetching(false); });
    };

    run(true);
    let timer: ReturnType<typeof setInterval> | undefined;
    if (opts.refreshMs) {
      timer = setInterval(() => {
        if (!document.hidden) run(false);  // 分頁在背景時不打 API
      }, opts.refreshMs);
    }
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, fetching, loading: data === null && error === null };
}
