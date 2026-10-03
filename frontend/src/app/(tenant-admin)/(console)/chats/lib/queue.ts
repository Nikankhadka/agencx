import type { ConversationSummary } from "@/lib/api-schemas";

/**
 * RF-14/D38: the browser-free half of the Chats queue. Nothing here touches
 * React, fetch, or the DOM, so vitest (node, no jsdom) can pin the URL shape
 * and the waiting-time rule directly; the hook and the rendering are covered
 * by E2E.
 *
 * The filter is a server query over the whole tenant dataset - the client no
 * longer filters the rows it happens to hold. `needs_you` is the D38
 * definition (an open escalation or a taken-over thread) and is the default
 * tab; All, Unread, and Human handled are retained alongside it.
 */
export type QueueFilter = "needs_you" | "all" | "unread" | "human";

export const FILTERS: { id: QueueFilter; label: string }[] = [
  { id: "needs_you", label: "Needs you" },
  { id: "all", label: "All" },
  { id: "unread", label: "Unread" },
  { id: "human", label: "Human handled" },
];

/** RF-14 page size - one page is 50 rows, matching the backend default. */
export const PAGE_SIZE = 50;

/**
 * The list URL for one page. `URLSearchParams` handles both the query
 * encoding and an empty `q` (dropped), and the backend treats whitespace-only
 * `q` as no search, so a blank box never adds a `q`.
 */
export function queuePath(filter: QueueFilter, q: string, offset: number): string {
  const params = new URLSearchParams({ filter, limit: String(PAGE_SIZE), offset: String(offset) });
  const needle = q.trim();
  if (needle) params.set("q", needle);
  return `/api/conversations?${params.toString()}`;
}

/**
 * When a row is waiting, the time is the escalation's own stamp - that is what
 * "waiting" means. Otherwise it is the last activity, falling back to when the
 * conversation started so a brand-new empty thread still shows a time.
 */
export function waitingTimeOf(row: ConversationSummary): string {
  if (row.needs_attention) return row.pending_since ?? row.last_activity_at ?? row.created_at;
  return row.last_activity_at ?? row.created_at;
}
