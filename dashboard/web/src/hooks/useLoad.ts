import { useEffect, useState } from "react";

type Options = {
  /** deps 變更時保留舊資料直到新資料抵達(stale-while-revalidate),
   *  避免圖表卸載重掛造成閃爍。 */
  keepPrevious?: boolean;
};

/** 通用資料載入 hook:載入中 / 錯誤 / 資料三態 + 換頁重取。 */
export function useLoad<T>(
  loader: () => Promise<T>,
  deps: unknown[] = [],
  opts: Options = {},
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    if (!opts.keepPrevious) setData(null);
    setError(null);
    setFetching(true);
    let cancelled = false; // 快速連點時丟棄過期回應,避免競態
    loader()
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setFetching(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, fetching, loading: data === null && error === null };
}
