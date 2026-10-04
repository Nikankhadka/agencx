import { describe, expect, it } from "vitest";
import type { ConversationSummary } from "@/lib/api-schemas";
import { FILTERS, PAGE_SIZE, queuePath, waitingTimeOf } from "./queue";

function row(overrides: Partial<ConversationSummary>): ConversationSummary {
  return {
    id: "4f9a2c18-0b7e-4d3a-9c21-77a1b2c3d4e5",
    customer_ref: null,
    status: "open",
    created_at: "2026-10-01T00:00:00Z",
    message_count: 0,
    needs_attention: false,
    unread: false,
    handler: "assistant",
    waiting_on_customer: false,
    ...overrides,
  };
}

describe("FILTERS", () => {
  it("opens on Action needed and keeps the other three", () => {
    expect(FILTERS.map((filter) => filter.id)).toEqual(["needs_you", "unread", "all", "resolved"]);
    expect(FILTERS[0]!.label).toBe("Action needed");
  });
});

describe("queuePath", () => {
  it("carries the filter, page size, and offset", () => {
    expect(queuePath("needs_you", "", 0)).toBe(
      `/api/conversations?filter=needs_you&limit=${PAGE_SIZE}&offset=0`,
    );
    expect(queuePath("resolved", "", 50)).toBe(
      `/api/conversations?filter=resolved&limit=${PAGE_SIZE}&offset=50`,
    );
  });

  it("adds a trimmed q and drops a blank one", () => {
    expect(queuePath("all", "  Emma  ", 0)).toContain("q=Emma");
    expect(queuePath("all", "   ", 0)).not.toContain("q=");
  });

  it("encodes a query with spaces and symbols", () => {
    expect(queuePath("all", "a&b c", 0)).toContain("q=a%26b+c");
  });
});

describe("waitingTimeOf", () => {
  it("uses the escalation stamp when the row needs attention", () => {
    const waiting = row({
      needs_attention: true,
      pending_since: "2026-09-30T10:00:00Z",
      last_activity_at: "2026-10-02T10:00:00Z",
    });
    expect(waitingTimeOf(waiting)).toBe("2026-09-30T10:00:00Z");
  });

  it("uses last activity when nothing is waiting", () => {
    expect(waitingTimeOf(row({ last_activity_at: "2026-10-02T10:00:00Z" }))).toBe(
      "2026-10-02T10:00:00Z",
    );
  });

  it("falls back to created_at when there is no activity", () => {
    expect(waitingTimeOf(row({ last_activity_at: null }))).toBe("2026-10-01T00:00:00Z");
  });

  it("falls back past a null pending_since without collapsing it to an epoch", () => {
    const waiting = row({
      needs_attention: true,
      pending_since: null,
      last_activity_at: "2026-10-02T10:00:00Z",
    });
    expect(waitingTimeOf(waiting)).toBe("2026-10-02T10:00:00Z");
  });
});
