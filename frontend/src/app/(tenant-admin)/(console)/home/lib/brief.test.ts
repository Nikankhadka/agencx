import { describe, expect, it } from "vitest";
import { buildBrief } from "./brief";
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

  it("names the one customer who is waiting, and why", () => {
    const items = buildBrief(
      [
        conversation({
          needs_attention: true,
          customer_ref: "Emma W.",
          pending_summary: "Wants a price for 15 people.",
        }),
      ],
      [record()],
    );
    expect(items).toHaveLength(1);
    expect(items[0]!.kind).toBe("waiting");
    expect(items[0]!.headline).toBe("Emma W. is waiting on you.");
    expect(items[0]!.note).toBe("Wants a price for 15 people.");
    expect(items[0]!.chips[0]!.href).toBe("/chats");
  });

  it("counts them once there is more than one", () => {
    const items = buildBrief(
      [
        conversation({ id: "a", needs_attention: true }),
        conversation({ id: "b", needs_attention: true }),
        conversation({ id: "c" }),
      ],
      [record()],
    );
    expect(items[0]!.headline).toBe("2 customers are waiting on you.");
  });

  it("falls back when the customer has no name", () => {
    const items = buildBrief([conversation({ needs_attention: true })], [record()]);
    expect(items[0]!.headline).toBe("A customer is waiting on you.");
    expect(items[0]!.note).toBeUndefined();
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

  it("puts the waiting customer above the draft", () => {
    const items = buildBrief(
      [conversation({ needs_attention: true })],
      [record({ status: "draft" })],
    );
    expect(items.map((i) => i.kind)).toEqual(["waiting", "draft"]);
  });
});
