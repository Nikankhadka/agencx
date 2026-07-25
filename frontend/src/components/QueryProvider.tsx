"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";

/**
 * App-wide TanStack Query provider. The console pages fetch server state
 * through it (caching, dedup, retry, background refetch) instead of each
 * reimplementing a loading/error/data triad with a manual `let active` flag.
 *
 * The client is created once per browser session (useState initializer) so it
 * isn't recreated on every render. Rendered from the root layout, so it's
 * available on every surface - the customer chat surface simply doesn't use it.
 */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // A console list stays fresh for 30s; navigating away and back
            // within that window serves the cache instead of refetching.
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // Retry transient failures, but never a 4xx - a 401/403/404 won't
            // fix itself on retry, so failing fast shows the real error sooner.
            retry: (failureCount, error) => {
              if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
                return false;
              }
              return failureCount < 2;
            },
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
