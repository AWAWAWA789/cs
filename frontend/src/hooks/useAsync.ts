import { useCallback, useEffect, useRef, useState } from "react";

interface AsyncState<T> {
  /** 最近一次成功的数据，加载新数据时保留（stale-while-revalidate）。 */
  data: T | null;
  /** 是否正在加载（首次加载或刷新）。 */
  loading: boolean;
  /** 是否正在后台刷新（已有旧数据，正在获取新数据）。 */
  isStale: boolean;
  /** 错误信息。 */
  error: string | null;
}

/**
 * 通用异步数据 Hook，实现 stale-while-revalidate 模式。
 *
 * - 首次加载：data=null, loading=true
 * - 参数变化刷新：保留旧 data，loading=false, isStale=true
 * - 新数据到达：更新 data, isStale=false
 * - 请求自动取消：切换参数时取消上一个未完成的请求（AbortController）
 * - 懒加载：当 enabled=false 时不发起请求，enabled 变为 true 时自动触发
 *
 * @param fn 异步函数，接收 AbortSignal 参数用于取消请求
 * @param deps 依赖数组，变化时自动重新请求
 * @param enabled 是否启用请求（默认 true），为 false 时不发起请求
 */
export function useAsync<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
  enabled: boolean = true,
): AsyncState<T> & { refetch: () => void } {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: enabled,
    isStale: false,
    error: null,
  });
  const [counter, setCounter] = useState(0);
  /** 保留上一次成功的数据引用，用于 stale-while-revalidate。 */
  const prevDataRef = useRef<T | null>(null);

  const refetch = useCallback(() => setCounter((c) => c + 1), []);

  useEffect(() => {
    // 当 enabled 为 false 时不发起请求
    if (!enabled) {
      setState({
        data: null,
        loading: false,
        isStale: false,
        error: null,
      });
      return;
    }

    // 创建 AbortController 用于取消旧请求
    const controller = new AbortController();
    let cancelled = false;

    // 判断是否为首次加载（无旧数据）还是刷新（有旧数据）
    const hasPrevData = prevDataRef.current !== null;
    setState((prev) => ({
      data: prev.data, // 保留旧数据
      loading: !hasPrevData, // 首次加载才显示全屏 loading
      isStale: hasPrevData, // 有旧数据时标记为 stale
      error: null,
    }));

    fn(controller.signal)
      .then((data) => {
        if (cancelled || controller.signal.aborted) return;
        prevDataRef.current = data;
        setState({ data, loading: false, isStale: false, error: null });
      })
      .catch((err) => {
        if (cancelled || controller.signal.aborted) return;
        // AbortError 不作为错误展示
        if (err?.name === "AbortError") return;
        setState((prev) => ({
          data: prev.data, // 保留旧数据
          loading: false,
          isStale: false,
          error: err?.message ?? String(err),
        }));
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, counter, enabled]);

  return { ...state, refetch };
}
