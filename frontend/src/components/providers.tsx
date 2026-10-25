"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api";

// Any API call answered with 401 means the session has expired or been
// revoked: send the user to sign in, then back to where they were.
function redirectOnUnauthorized(error: unknown) {
  if (error instanceof ApiError && error.status === 401 && window.location.pathname !== "/login") {
    const next = window.location.pathname + window.location.search;
    // Full page load on purpose: it also discards hidden pages and cached data
    // from the expired session. (No router is available here, outside React.)
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${encodeURIComponent(next)}`);
  }
}

export function Providers({ children }: { children: ReactNode }) {
  // One client per browser tab, created once (not on every render).
  const [queryClient] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({ onError: redirectOnUnauthorized }),
        mutationCache: new MutationCache({ onError: redirectOnUnauthorized }),
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            // Retrying a 404 or 401 can't help; retry only network/server errors.
            retry: (failureCount, error) =>
              failureCount < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
          },
        },
      }),
  );
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
