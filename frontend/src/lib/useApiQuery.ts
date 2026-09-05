import { useQuery } from "@tanstack/react-query";
import { apiFetch, ApiError } from "./api";

/**
 * Thin `useQuery` wrapper that fetches `path` through `apiFetch` (bearer token +
 * ApiError + 422 parsing), replacing the hand-rolled loading/error/`let active`
 * triad the console pages used to each reimplement. Caching, dedup, retry and
 * background refetch come from the shared QueryClient (see QueryProvider).
 *
 * The query key defaults to `[path]`; pass `queryKey` with the param values
 * (e.g. a status filter) so each variant caches and refetches independently.
 */
export function useApiQuery<T>(
  path: string,
  options?: { queryKey?: readonly unknown[]; enabled?: boolean; refetchInterval?: number },
) {
  return useQuery<T, ApiError>({
    queryKey: options?.queryKey ?? [path],
    queryFn: () => apiFetch<T>(path),
    enabled: options?.enabled,
    refetchInterval: options?.refetchInterval,
  });
}

/** Turn a query error into the backend `detail` string, or a fallback. */
export function errorMessage(error: unknown, fallback: string): string | null {
  if (!error) return null;
  return error instanceof ApiError ? error.detail : fallback;
}
