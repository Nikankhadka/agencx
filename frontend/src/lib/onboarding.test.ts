import { describe, expect, it } from "vitest";
import {
  ACCEPTED_UPLOAD_EXTENSIONS,
  describeUpload,
  foldReply,
  parseOnboardingEvent,
  uploadTargetForStage,
} from "./onboarding";

describe("parseOnboardingEvent", () => {
  it("parses a token event", () => {
    expect(parseOnboardingEvent('{"type":"token","text":"hi"}')).toEqual({
      type: "token",
      text: "hi",
    });
  });

  it("parses a state event with the beat key", () => {
    const event = parseOnboardingEvent(
      '{"type":"state","stage":"business_name","draft":{"owner_display_name":"Sam"},"completed":false,"input":{"kind":"text","placeholder":"What is your business called?","chips":[],"mask":null,"cta_label":null},"can_confirm":false}',
    );
    expect(event?.type).toBe("state");
    if (event?.type === "state") {
      expect(event.stage).toBe("business_name");
      expect(event.input?.kind).toBe("text");
      expect(event.draft.owner_display_name).toBe("Sam");
    }
  });

  it("returns null for a malformed (partial) frame instead of throwing", () => {
    expect(parseOnboardingEvent('{"type":"tok')).toBeNull();
  });

  it("returns null for valid JSON that is not an object with a string type", () => {
    expect(parseOnboardingEvent('"a string"')).toBeNull();
    expect(parseOnboardingEvent("7")).toBeNull();
    expect(parseOnboardingEvent("null")).toBeNull();
    expect(parseOnboardingEvent('{"no":"type"}')).toBeNull();
  });
});

describe("foldReply", () => {
  it("accumulates token deltas into the reply", () => {
    const tokens = ["Hello", ", ", "world"];
    const reply = tokens.reduce(
      (acc, text) => foldReply(acc, { type: "token", text }),
      "",
    );
    expect(reply).toBe("Hello, world");
  });

  it("clears accumulated text on redraft (price-echo guard tripped)", () => {
    const afterFirst = foldReply("", { type: "token", text: "bad price" });
    expect(afterFirst).toBe("bad price");
    expect(foldReply(afterFirst, { type: "redraft", reason: "echo" })).toBe("");
  });

  it("reconciles the full reply event to the same text the tokens built", () => {
    const fromTokens = foldReply("Hello", { type: "token", text: "!" });
    expect(foldReply(fromTokens, { type: "reply", text: "Hello!" })).toBe(
      "Hello!",
    );
  });

  it("ignores non-text events", () => {
    expect(foldReply("abc", { type: "done" })).toBe("abc");
    expect(foldReply("abc", { type: "progress", stage: "processing" })).toBe(
      "abc",
    );
  });
});

describe("describeUpload", () => {
  it("acknowledges every extension the backend accepts", () => {
    for (const ext of ACCEPTED_UPLOAD_EXTENSIONS) {
      const verdict = describeUpload(`menu${ext}`);
      expect(verdict.accepted).toBe(true);
      expect(verdict.message).toContain(`menu${ext}`);
    }
  });

  it("is case-insensitive about the extension", () => {
    expect(describeUpload("MENU.PDF").accepted).toBe(true);
  });

  it("refuses images by name, because nothing in the stack reads one", () => {
    const verdict = describeUpload("menu-photo.jpg");
    expect(verdict.accepted).toBe(false);
    expect(verdict.message).toContain("can't read images");
    // Every refusal names a way forward - it never just says no.
    expect(verdict.message).toContain("link");
  });

  it("refuses an unknown type without pretending to know what it is", () => {
    const verdict = describeUpload("prices.xlsx");
    expect(verdict.accepted).toBe(false);
    expect(verdict.message).toContain("prices.xlsx");
  });

  it("handles a file with no extension", () => {
    expect(describeUpload("prices").accepted).toBe(false);
  });
});

describe("uploadTargetForStage", () => {
  it("sends a file attached at the source stage to the source endpoint", () => {
    expect(uploadTargetForStage("knowledge")).toEqual({
      endpoint: "/api/onboarding/source",
      mergesProfile: true,
    });
  });

  it("treats the name question as the source stage, because the source is next", () => {
    // 29: the source ask sits immediately after the owner's name. A file
    // attached while the name is on screen is an answer to the source, not a
    // reviewable draft that leaves the source ask still pending.
    expect(uploadTargetForStage("owner_display_name")).toEqual({
      endpoint: "/api/onboarding/source",
      mergesProfile: true,
    });
  });

  it("keeps every other text stage on the knowledge drafts batch", () => {
    for (const stage of [
      "business_name",
      "business_type",
      "headcount",
      "hours",
      "services",
      "contact",
      "abn",
      "gst",
      "confirm",
      "",
    ]) {
      expect(uploadTargetForStage(stage)).toEqual({
        endpoint: "/api/knowledge/drafts/upload",
        mergesProfile: false,
      });
    }
  });
});
