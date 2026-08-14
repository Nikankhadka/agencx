"use client";

import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";

export interface ErrorRecoveryProps {
  /** Re-render the failed segment (Next's error-boundary retry). */
  onRetry: () => void;
  title?: string;
  description?: string;
}

/**
 * Branded fallback shown when a route segment throws while rendering. Shared by
 * every console's `error.tsx` so a client render error becomes a recoverable
 * panel instead of a white screen. Presentational only - all wiring (logging,
 * the retry callback) lives in the `error.tsx` boundary that renders this.
 */
export function ErrorRecovery({
  onRetry,
  title = "Something went wrong",
  description = "This page hit an unexpected error. You can try again - if it keeps happening, refresh or come back shortly.",
}: ErrorRecoveryProps) {
  return (
    <div
      role="alert"
      className="flex min-h-[60dvh] flex-col items-center justify-center gap-3 px-6 text-center"
    >
      <span
        className="flex h-10 w-10 items-center justify-center rounded-full bg-danger-subtle text-danger"
        aria-hidden="true"
      >
        <Icon name="cancel" size={22} />
      </span>
      <p className="text-title-3 font-medium text-text">{title}</p>
      <p className="max-w-sm text-body-sm text-text-secondary">{description}</p>
      <div className="mt-2">
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      </div>
    </div>
  );
}
