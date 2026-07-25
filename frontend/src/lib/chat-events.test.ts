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
