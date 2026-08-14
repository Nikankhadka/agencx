import type { ReactNode } from "react";

export type ChatRole = "customer" | "assistant" | "human_agent" | "system";

export interface ChatBubbleProps {
  role: ChatRole;
  children: ReactNode;
}

const ROLE_CLASSES: Record<ChatRole, string> = {
  customer: "self-end bg-bubble-out text-text-inverse",
  assistant: "self-start bg-bubble-in text-text",
  human_agent: "self-start bg-bubble-agent-in text-text",
  system: "self-center bg-transparent text-text-tertiary text-footnote",
};

// The 4px corner always points at the speaker: inbound (assistant) tips
// top-left, outbound (owner/customer) tips top-right (prototype v6 L146-148).
const RADIUS_CLASSES: Record<ChatRole, string> = {
  customer:
    "rounded-[var(--radius-bubble)_var(--radius-bubble-tip)_var(--radius-bubble)_var(--radius-bubble)]",
  assistant:
    "rounded-[var(--radius-bubble-tip)_var(--radius-bubble)_var(--radius-bubble)_var(--radius-bubble)]",
  human_agent:
    "rounded-[var(--radius-bubble-tip)_var(--radius-bubble)_var(--radius-bubble)_var(--radius-bubble)]",
  system: "",
};

/**
 * docs/design/frontend.md section 6 + Agencx prototype: owner/customer bubbles
 * (filled, right) with a top-right tip, assistant bubbles (light, left) with a
 * top-left tip, human_agent (light crimson, labeled), system (centered
 * caption). Streaming arrives with StreamingText.
 */
export function ChatBubble({ role, children }: ChatBubbleProps) {
  if (role === "system") {
    return <p className={`w-full text-center ${ROLE_CLASSES.system}`}>{children}</p>;
  }

  return (
    <div
      className={`max-w-[85%] px-4 py-2.5 text-body-sm leading-relaxed ${RADIUS_CLASSES[role]} ${ROLE_CLASSES[role]}`}
    >
      {role === "human_agent" ? (
        <p className="mb-1 text-footnote font-medium text-text-secondary">Human agent</p>
      ) : null}
      {children}
    </div>
  );
}
