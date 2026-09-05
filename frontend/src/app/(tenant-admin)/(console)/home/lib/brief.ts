import type { ConversationSummary } from "@/lib/api-schemas";
import {
  sourceLabel,
  type KnowledgeRecord,
} from "../../business/details/knowledge/lib/types";

/**
 * The brief: what wants the owner right now, as the prototype's
 * `addCard(hl, chips, note)` renders it - a headline, the action that resolves
 * it, and one quiet context line.
 *
 * Every kind here is backed by state that exists in Stage 1. The prototype's
 * brief is full of Stage 2 material (jobs, an overdue balance, a payment
 * reminder) and none of it is ported, because a card with nothing behind it is
 * the dead surface the PRD forbids. Stage 2's quote and order approvals become
 * further kinds in this same list - the card never changes.
 *
 * Waiting customers are not a `BriefItem` - see `waitingRows` below. A list of
 * customers is a different shape from a headline-plus-chips card, and one
 * BriefItem already collapsed every waiting customer into whichever one
 * happened to be first; the WaitingPanel this feeds shows every row.
 */
export interface BriefChip {
  label: string;
  href: string;
}

export interface BriefItem {
  kind: "draft" | "share";
  headline: string;
  note?: string;
  chips: BriefChip[];
}

export interface WaitingRow {
  id: string;
  name: string;
  summary: string;
  since: string;
}

function plural(n: number, one: string, many: string): string {
  return n === 1 ? one : many;
}

/** Shown for the seconds before the async escalation summariser lands its
 * result - never a reason-code map, since the summariser is what makes those
 * unnecessary. */
const SUMMARY_PENDING = "A summary is being prepared.";

/**
 * Every customer waiting on the owner, oldest escalation first - the
 * prioritisation the panel promises. `pending_since` is the escalation's own
 * timestamp (added alongside `pending_summary`); a row from before that
 * migration falls back to `last_activity_at` so it still sorts somewhere
 * sane rather than floating to a NaN-driven top or bottom.
 */
export function waitingRows(conversations: ConversationSummary[]): WaitingRow[] {
  return conversations
    .filter((row) => row.needs_attention)
    .map((row) => ({
      id: row.id,
      name: row.customer_ref?.trim() || "A customer",
      summary: row.pending_summary?.trim() || SUMMARY_PENDING,
      since: row.pending_since ?? row.last_activity_at ?? row.created_at,
    }))
    .sort((a, b) => new Date(a.since).getTime() - new Date(b.since).getTime());
}

/**
 * ponytail: composed on the client from the two endpoints that already serve
 * this state, rather than behind a new /api/brief. Two queries is not a reason
 * to build a route. When Stage 2 adds quote-approval and order-approval kinds
 * and the count grows, promote to one /api/brief returning this exact item
 * list - BriefItem is already that contract, so the change is server-side only.
 */
export function buildBrief(
  conversations: ConversationSummary[],
  records: KnowledgeRecord[],
): BriefItem[] {
  const items: BriefItem[] = [];

  // A draft answers nothing until it is saved (D19), so an unread one is the
  // owner's assistant sitting on knowledge it is not allowed to use yet.
  const drafts = records.filter((record) => record.status === "draft");
  if (drafts.length > 0) {
    const first = drafts[0]!;
    items.push({
      kind: "draft",
      headline:
        drafts.length === 1
          ? `${sourceLabel(first)} is read and waiting for you to check it.`
          : `${drafts.length} sources are read and waiting for you to check them.`,
      note: `Nothing here answers a customer until you save ${plural(
        drafts.length,
        "it",
        "them",
      )}.`,
      chips: [{ label: "Review", href: "/business/details/knowledge" }],
    });
  }

  // No conversation has ever happened, so the page has not reached anyone. The
  // honest signal for "not shared yet" without inventing a column to track it.
  if (conversations.length === 0) {
    items.push({
      kind: "share",
      headline: "Nobody has messaged you yet.",
      note: "Share your link and customers can ask anything you have written down.",
      chips: [{ label: "Get your link", href: "/business" }],
    });
  }

  return items;
}
