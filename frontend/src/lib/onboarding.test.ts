import { describe, expect, it } from "vitest";
import { isMultiSelect, parseOnboardingEvent } from "./onboarding";

describe("parseOnboardingEvent", () => {
  it("parses a token event", () => {
    expect(parseOnboardingEvent('{"type":"token","text":"hi"}')).toEqual({
      type: "token",
      text: "hi",
    });
  });

  it("parses a state event with the beat key", () => {
    const event = parseOnboardingEvent(
      '{"type":"state","stage":"team","draft":{"business":{"name":"Bytefix"}},"completed":false,"input":{"kind":"chips","placeholder":"Just you?","chips":[{"label":"Just me","value":"solo"}],"mask":null,"cta_label":null},"can_confirm":false}',
    );
    expect(event?.type).toBe("state");
    if (event?.type === "state") {
      expect(event.stage).toBe("team");
      expect(event.input?.kind).toBe("chips");
      expect(event.draft.business.name).toBe("Bytefix");
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

describe("isMultiSelect", () => {
  it("is true only for chips beats carrying a dashed chip", () => {
    expect(
      isMultiSelect({
        kind: "chips",
        placeholder: "",
        chips: [{ label: "My website", value: "website", dashed: true }],
        mask: null,
        cta_label: null,
      }),
    ).toBe(true);

    expect(
      isMultiSelect({
        kind: "chips",
        placeholder: "",
        chips: [{ label: "Yes", value: "yes" }],
        mask: null,
        cta_label: null,
      }),
    ).toBe(false);

    expect(
      isMultiSelect({
        kind: "text",
        placeholder: "",
        chips: [],
        mask: null,
        cta_label: null,
      }),
    ).toBe(false);
  });
});
