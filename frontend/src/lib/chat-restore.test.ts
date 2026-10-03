import { describe, expect, it } from "vitest";
import { cardFromResponse, messageFromPublic } from "./chat-restore";
import type { PublicMessage } from "./api-schemas";

const quote = {
  quote_id: "q-1",
  line_items: [
    {
      kind: "rule" as const,
      code: "screen-repair-a",
      label: "Screen repair (tier A)",
      quantity: 1,
      unit_amount_cents: 12000,
      line_total_cents: 12000,
    },
  ],
  subtotal_cents: 12000,
  tax_cents: 960,
  total_cents: 12960,
  status: "sent",
};

const summary = {
  line_items: [],
  subtotal_cents: 1500,
  tax_cents: 150,
  total_cents: 1650,
  disclaimer: "Prices are estimates.",
};

const catalog = {
  offerings: [
    {
      id: "off-1",
      name: "Tempered glass protector",
      description: "A protective layer",
      category: null,
      price_cents: 1500,
    },
  ],
};

function publicMessage(overrides: Partial<PublicMessage>): PublicMessage {
  return {
    id: "m-1",
    role: "assistant",
    content: "text",
    created_at: "2026-10-03T00:00:00Z",
    ...overrides,
  };
}

describe("cardFromResponse", () => {
  it("maps a formal quote payload", () => {
    expect(cardFromResponse({ type: "quote", quote })).toEqual({ quote });
  });

  it("maps a price-summary payload", () => {
    expect(cardFromResponse({ type: "price_summary", summary })).toEqual({
      priceSummary: summary,
    });
  });

  it("maps a catalog payload", () => {
    expect(cardFromResponse({ type: "catalog", catalog })).toEqual({ catalog });
  });

  it("yields no cards for null or undefined", () => {
    expect(cardFromResponse(null)).toEqual({});
    expect(cardFromResponse(undefined)).toEqual({});
  });

  it("yields no cards for an unknown type", () => {
    expect(cardFromResponse({ type: "mystery", quote })).toEqual({});
  });

  it("yields no cards when the payload is missing or the wrong shape", () => {
    expect(cardFromResponse({ type: "quote" })).toEqual({});
    expect(cardFromResponse({ type: "price_summary" })).toEqual({});
    expect(cardFromResponse({ type: "catalog" })).toEqual({});
    expect(cardFromResponse({ type: "quote", quote: "nope" })).toEqual({});
  });

  it("yields no cards for a non-dict response", () => {
    expect(cardFromResponse("quote")).toEqual({});
    expect(cardFromResponse(42)).toEqual({});
    expect(cardFromResponse(true)).toEqual({});
    expect(cardFromResponse(["quote"])).toEqual({});
  });

  it("yields no cards for an array response", () => {
    // An array is not a card object: it has no `type` and its payload checks
    // would otherwise read array indices as fields.
    expect(cardFromResponse([])).toEqual({});
    expect(cardFromResponse([{ type: "quote", quote: { line_items: [] } }])).toEqual({});
  });

  it("never throws when a card payload is missing its iterable", () => {
    // QuoteCard/PriceSummaryCard/CatalogCard call `.map`/iterate the payload;
    // a shape without the array would crash the restore render. Each must
    // degrade to no card instead.
    const malformed = [
      { type: "quote", quote: [] },
      { type: "quote", quote: {} },
      { type: "price_summary", summary: {} },
      { type: "price_summary", summary: [] },
      { type: "catalog", catalog: {} },
      { type: "catalog", catalog: [] },
      { type: "quote" },
      { type: "price_summary" },
      { type: "catalog" },
    ];
    for (const response of malformed) {
      expect(() => cardFromResponse(response)).not.toThrow();
      expect(cardFromResponse(response)).toEqual({});
    }
  });
});

describe("messageFromPublic", () => {
  it("maps role, content, and the restored card", () => {
    const message = messageFromPublic(
      publicMessage({ role: "assistant", content: "Here it is.", response: { type: "quote", quote } }),
    );
    expect(message).toEqual({
      role: "assistant",
      text: "Here it is.",
      quote,
    });
  });

  it("restores a plain text turn with no card", () => {
    expect(messageFromPublic(publicMessage({ content: "We are open 9-5." }))).toEqual({
      role: "assistant",
      text: "We are open 9-5.",
    });
  });
});
