import { useCallback, useEffect, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/**
 * Generic async data hook with manual refetch support.
 */
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
): AsyncState<T> & { refetch: () => void } {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: true,
    error: null,
  });
  const [counter, setCounter] = useState(0);

  const refetch = useCallback(() => setCounter((c) => c + 1), []);

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });
    fn()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({ data: null, loading: false, error: err?.message ?? String(err) });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, counter]);

  return { ...state, refetch };
}
