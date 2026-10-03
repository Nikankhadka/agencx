import { describe, expect, it } from "vitest";
import { handoffRequestBody, shouldShowAskForPerson } from "./handoff";

describe("handoffRequestBody", () => {
  it("omits conversation_id when there is no conversation yet", () => {
    // The endpoint creates the conversation; a customer may want a person
    // before typing anything.
    expect(handoffRequestBody("bytefix", null)).toEqual({ slug: "bytefix" });
  });

  it("carries the conversation id when there is one", () => {
    expect(handoffRequestBody("bytefix", "conv-1")).toEqual({
      slug: "bytefix",
      conversation_id: "conv-1",
    });
  });
});

describe("shouldShowAskForPerson", () => {
  it("shows the control in the live composer", () => {
    expect(shouldShowAskForPerson({ escalated: false, handoffSeen: false })).toBe(true);
  });

  it("hides it once a handoff is already open", () => {
    // Idempotent: firing it again would ask a second time.
    expect(shouldShowAskForPerson({ escalated: false, handoffSeen: true })).toBe(false);
  });

  it("hides it in the terminal escalated state", () => {
    expect(shouldShowAskForPerson({ escalated: true, handoffSeen: false })).toBe(false);
  });
});
