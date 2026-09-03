import { describe, expect, it } from "vitest";
import { parseChatStreamEvent } from "./chat-events";

describe("parseChatStreamEvent", () => {
  it("parses a token event", () => {
    const event = parseChatStreamEvent('{"type":"token","text":"hi"}');
    expect(event).toEqual({ type: "token", text: "hi" });
  });

  it("parses a citations event", () => {
    const event = parseChatStreamEvent(
      '{"type":"citations","citations":[{"index":1,"source":"faq.md","snippet":"x"}]}',
    );
    expect(event?.type).toBe("citations");
  });

  it("returns null for a malformed (partial) frame instead of throwing", () => {
    // A frame split mid-JSON must not abort the stream.
    expect(parseChatStreamEvent('{"type":"tok')).toBeNull();
  });

  it("returns null for valid JSON that is not an object with a string type", () => {
    expect(parseChatStreamEvent('"just a string"')).toBeNull();
    expect(parseChatStreamEvent("42")).toBeNull();
    expect(parseChatStreamEvent("null")).toBeNull();
    expect(parseChatStreamEvent('{"no":"type"}')).toBeNull();
  });

  it("preserves the conversation id", () => {
    const event = parseChatStreamEvent('{"type":"conversation","conversation_id":"abc-123"}');
    expect(event).toEqual({ type: "conversation", conversation_id: "abc-123" });
  });
});

/**
 * C-5 split one flag in two, and these are the events that carry the split: a
 * `handoff` leaves the composer live, an `escalated` locks it. Nothing tested
 * them, so the distinction that took a working chat off a dead end rested on
 * two untested switch arms.
 */
describe("handoff vs escalated", () => {
  it("parses a handoff, which does not end the conversation", () => {
    expect(parseChatStreamEvent('{"type":"handoff"}')).toEqual({ type: "handoff" });
  });

  it("parses an escalated, the one terminal event", () => {
    expect(parseChatStreamEvent('{"type":"escalated"}')).toEqual({ type: "escalated" });
  });

  it("keeps them distinct - a handoff must never read as terminal", () => {
    const handoff = parseChatStreamEvent('{"type":"handoff"}');
    expect(handoff?.type).not.toBe("escalated");
  });

  it("carries refusal text through verbatim, since the backend owns that copy", () => {
    const event = parseChatStreamEvent(
      '{"type":"refusal","text":"I have asked someone from the business to take a look."}',
    );
    expect(event).toEqual({
      type: "refusal",
      text: "I have asked someone from the business to take a look.",
    });
  });
});
