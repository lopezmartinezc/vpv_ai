"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";

interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: boolean;
}

export function useFetch<T>(path: string | null): UseFetchResult<T> {
  const [result, setResult] = useState<{
    data: T | null;
    error: boolean;
    forPath: string | null;
  }>({ data: null, error: false, forPath: null });

  useEffect(() => {
    if (!path) return;

    let cancelled = false;

    apiClient
      .get<T>(path)
      .then((data) => {
        if (!cancelled) setResult({ data, error: false, forPath: path });
      })
      .catch(() => {
        if (!cancelled) setResult({ data: null, error: true, forPath: path });
      });

    return () => {
      cancelled = true;
    };
  }, [path]);

  const loading = path !== null && result.forPath !== path;

  return {
    data: loading ? null : result.data,
    loading,
    error: loading ? false : result.error,
  };
}
