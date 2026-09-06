import { describe, expect, it } from "vitest";
import { conversationRef, customerLabel } from "./format";

describe("conversationRef", () => {
  it("takes the head of the uuid, so it matches the id in the URL", () => {
    expect(conversationRef("4f9a2c18-0b7e-4d3a-9c21-77a1b2c3d4e5")).toBe("#4F9A2C");
  });

  it("distinguishes two conversations that share a prefix nowhere near the head", () => {
    expect(conversationRef("00000000-0000-4000-8000-000000000001")).toBe("#000000");
    expect(conversationRef("a1b2c3d4-0000-4000-8000-000000000001")).toBe("#A1B2C3");
  });

  it("tolerates an id shorter than six characters rather than padding it", () => {
    expect(conversationRef("c1")).toBe("#C1");
  });
});

describe("customerLabel", () => {
  it("uses the name when the customer gave one - it already identifies the row", () => {
    expect(customerLabel("Emma W.", "4f9a2c18-0b7e-4d3a-9c21-77a1b2c3d4e5")).toBe("Emma W.");
  });

  it("falls back to the reference when there is no name", () => {
    expect(customerLabel(null, "4f9a2c18-0b7e-4d3a-9c21-77a1b2c3d4e5")).toBe("#4F9A2C");
    expect(customerLabel(undefined, "c1")).toBe("#C1");
  });

  it("treats a blank customer_ref as no name, not as an empty label", () => {
    expect(customerLabel("   ", "c1")).toBe("#C1");
  });

  it("trims a name that arrived with padding", () => {
    expect(customerLabel("  Emma W. ", "c1")).toBe("Emma W.");
  });
});
