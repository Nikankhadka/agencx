"use client";

import { useEffect } from "react";
import { ErrorRecovery } from "@/components/ErrorRecovery";

/**
 * Error boundary for the tenant-admin console. Wraps every authed console page
 * so a client render error shows a branded, recoverable panel inside the app
 * shell instead of a white screen. `unstable_retry` re-renders the segment
 * (Next 16.2+).
 */
export default function ConsoleError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return <ErrorRecovery onRetry={unstable_retry} />;
}
