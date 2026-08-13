import type { ReactNode } from "react";
import { ThinkingDots } from "./ThinkingDots";

export interface StreamingTextProps {
  streaming: boolean;
  /**
   * Streaming and no content yet - the agent is still working on the first
   * token. Renders the ThinkingDots indicator instead of the empty text.
   */
  pending?: boolean;
  children: ReactNode;
}

/**
 * docs/design/frontend.md section 6: renders SSE tokens with a caret pulse
 * while streaming; `aria-live="polite"` so assistive tech announces new
 * text without interrupting. Interrupted/retry is the caller's concern
 * (rendered as a sibling affordance in the bubble, not by this component).
 */
export function StreamingText({ streaming, pending = false, children }: StreamingTextProps) {
  return (
    <span aria-live="polite">
      {pending ? (
        <ThinkingDots />
      ) : (
        <>
          {children}
          {streaming ? (
            <span
              className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-text align-middle"
              aria-hidden="true"
            />
          ) : null}
        </>
      )}
    </span>
  );
}
