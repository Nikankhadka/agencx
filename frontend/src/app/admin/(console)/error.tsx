"use client";

import { useEffect } from "react";
import { ErrorRecovery } from "@/components/ErrorRecovery";

/**
 * Error boundary for the platform (admin-surface) console. Same branded,
 * recoverable fallback as the tenant-admin console; `unstable_retry`
 * re-renders the failed segment (Next 16.2+).
 */
export default function PlatformConsoleError({
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
