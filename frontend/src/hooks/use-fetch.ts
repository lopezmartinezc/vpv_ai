"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiClientError, apiClient } from "@/lib/api-client";

interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: boolean;
  /**
   * The HTTP status the server answered with, when it answered one. Lets a page
   * tell "you may not see this yet" (403) from "it could not be loaded".
   */
  errorStatus: number | null;
  refetch: () => void;
}

export function useFetch<T>(path: string | null): UseFetchResult<T> {
  const [result, setResult] = useState<{
    data: T | null;
    error: boolean;
    errorStatus: number | null;
    forPath: string | null;
  }>({ data: null, error: false, errorStatus: null, forPath: null });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!path) return;

    let cancelled = false;

    apiClient
      .get<T>(path)
      .then((data) => {
        if (!cancelled) setResult({ data, error: false, errorStatus: null, forPath: path });
      })
      .catch((e: unknown) => {
        if (!cancelled)
          setResult({
            data: null,
            error: true,
            errorStatus: e instanceof ApiClientError ? e.status : null,
            forPath: path,
          });
      });

    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  const loading = path !== null && result.forPath !== path;

  return {
    data: loading ? null : result.data,
    loading,
    error: loading ? false : result.error,
    errorStatus: loading ? null : result.errorStatus,
    refetch,
  };
}
