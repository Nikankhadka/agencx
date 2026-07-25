import type { Citation } from "@/components/ui/CitationChip";
import type { QuotePayload } from "@/components/ui/QuoteCard";

/**
 * The customer-chat SSE protocol, mirroring the events the backend emits in
 * app/api/chat.py (`_sse`) and the agent nodes' stream writer. Previously every
 * event was accessed off a bare `JSON.parse` as `any`; this discriminated union
 * types each branch so the chat loop can't silently read a wrong field, and the
 * parser below is the one guarded entry point (a malformed or partial frame
 * must never abort an in-progress stream).
 */
export type ChatStreamEvent =
  | { type: "conversation"; conversation_id: string }
  | { type: "citations"; citations: Citation[] }
  | { type: "quote"; quote: QuotePayload }
  | { type: "redraft" }
  | { type: "token"; text: string }
  | { type: "refusal"; text: string }
  | { type: "escalated" }
  | { type: "done" };

/**
 * Parse one SSE `data:` payload into a typed event, or `null` if it is not
 * valid JSON with a string `type`. Returning `null` (rather than throwing) lets
 * the caller skip a bad frame and keep reading the stream.
 */
export function parseChatStreamEvent(payload: string): ChatStreamEvent | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch {
    return null;
  }
  if (
    parsed !== null &&
    typeof parsed === "object" &&
    typeof (parsed as { type?: unknown }).type === "string"
  ) {
    return parsed as ChatStreamEvent;
  }
  return null;
}
