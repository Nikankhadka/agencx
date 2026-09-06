import { describe, expect, it } from "vitest";
import { buildBrief, waitingRows } from "./brief";
import type { ConversationSummary } from "@/lib/api-schemas";
import type { KnowledgeRecord } from "../../business/details/knowledge/lib/types";

function conversation(over: Partial<ConversationSummary> = {}): ConversationSummary {
  return {
    id: "c1",
    customer_ref: null,
    status: "open",
    created_at: "2026-08-22T09:00:00Z",
    message_count: 2,
    needs_attention: false,
    ...over,
  } as ConversationSummary;
}

describe("waitingRows", () => {
  it("names the waiting customer, their summary, and when they were raised", () => {
    const rows = waitingRows([
      conversation({
        id: "c1",
        needs_attention: true,
        customer_ref: "Emma W.",
        pending_summary: "Wants a price for 15 people.",
        pending_since: "2026-08-22T09:00:00Z",
      }),
    ]);
    expect(rows).toEqual([
      { id: "c1", name: "Emma W.", summary: "Wants a price for 15 people.", since: "2026-08-22T09:00:00Z" },
    ]);
  });

  it("ignores conversations that do not need attention", () => {
    expect(waitingRows([conversation({ needs_attention: false })])).toEqual([]);
  });

  it("falls back to the conversation's short reference when there is no name", () => {
    const rows = waitingRows([conversation({ needs_attention: true })]);
    expect(rows[0]!.name).toBe("#C1");
  });

  it("shows a placeholder line before the async summary lands", () => {
    const rows = waitingRows([
      conversation({ needs_attention: true, pending_summary: null }),
    ]);
    expect(rows[0]!.summary).toBe("A summary is being prepared.");
  });

  it("sorts oldest escalation first", () => {
    const rows = waitingRows([
      conversation({ id: "newer", needs_attention: true, pending_since: "2026-08-22T09:10:00Z" }),
      conversation({ id: "older", needs_attention: true, pending_since: "2026-08-22T09:00:00Z" }),
    ]);
    expect(rows.map((r) => r.id)).toEqual(["older", "newer"]);
  });

  it("falls back to last_activity_at, then created_at, when pending_since is missing", () => {
    const rows = waitingRows([
      conversation({
        id: "no-pending-since",
        needs_attention: true,
        created_at: "2026-08-22T08:00:00Z",
        last_activity_at: "2026-08-22T09:30:00Z",
      }),
      conversation({
        id: "with-pending-since",
        needs_attention: true,
        pending_since: "2026-08-22T09:15:00Z",
      }),
    ]);
    // 09:15 (pending_since) sorts before 09:30 (last_activity_at fallback).
    expect(rows.map((r) => r.id)).toEqual(["with-pending-since", "no-pending-since"]);
  });
});

function record(over: Partial<KnowledgeRecord> = {}): KnowledgeRecord {
  return {
    id: "d1",
    filename: "menu.pdf",
    doc_type: "other",
    status: "ready",
    error: null,
    sections: [],
    ...over,
  };
}

describe("buildBrief", () => {
  it("is empty when a live business has nothing outstanding", () => {
    expect(buildBrief([conversation()], [record()])).toEqual([]);
  });

  it("surfaces an unsaved draft by its source, not its filename when it is a link", () => {
    const items = buildBrief(
      [conversation()],
      [record({ status: "draft", filename: "https://sababa.example/menu" })],
    );
    expect(items).toHaveLength(1);
    expect(items[0]!.kind).toBe("draft");
    expect(items[0]!.headline).toBe("sababa.example is read and waiting for you to check it.");
    expect(items[0]!.note).toContain("until you save it");
    expect(items[0]!.chips[0]!.href).toBe("/business/details/knowledge");
  });

  it("counts drafts and pluralises the note with them", () => {
    const items = buildBrief(
      [conversation()],
      [record({ id: "a", status: "draft" }), record({ id: "b", status: "draft" })],
    );
    expect(items[0]!.headline).toBe("2 sources are read and waiting for you to check them.");
    expect(items[0]!.note).toContain("until you save them");
  });

  it("ignores records that are not drafts", () => {
    expect(
      buildBrief([conversation()], [record({ status: "failed" }), record({ id: "b" })]),
    ).toEqual([]);
  });

  it("nudges sharing only while no customer has ever written", () => {
    const items = buildBrief([], []);
    expect(items).toHaveLength(1);
    expect(items[0]!.kind).toBe("share");
    expect(items[0]!.chips[0]!.href).toBe("/business");

    expect(buildBrief([conversation()], []).some((i) => i.kind === "share")).toBe(false);
  });
});
