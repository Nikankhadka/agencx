import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CatalogCard, type CatalogPayload } from "./CatalogCard";
import { PriceSummaryCard, type PriceSummaryPayload } from "./PriceSummaryCard";
import { QuoteCard, type QuotePayload } from "./QuoteCard";

/**
 * RF-9: the offering, price-summary, and quote cards are one visual family.
 * They must render at the same width (`max-w-[520px]`, the value
 * `design/frontend.md` section 4.7 already accepts) with the same chrome
 * (`Card`'s rounded-card / border-hairline / bg-surface / p-4) and the same
 * header treatment (`h3` with text-body / font-semibold / text-text), so they
 * left-align in one column in the chat thread.
 *
 * The assertions parse the rendered HTML rather than pinning whole strings, so
 * a change to unrelated card markup does not fail this file for the wrong
 * reason - it only guards the shared outer class and the shared header.
 */

const catalog: CatalogPayload = {
  offerings: [
    { id: "1", name: "Screen repair", description: "Genuine part", category: "Repairs", price_cents: 8900 },
  ],
};

const summary: PriceSummaryPayload = {
  line_items: [
    {
      kind: "item",
      item_id: "1",
      label: "Screen repair",
      quantity: 1,
      unit_amount_cents: 8900,
      line_total_cents: 8900,
    },
  ],
  subtotal_cents: 8900,
  tax_cents: 0,
  total_cents: 8900,
  disclaimer: "Based on the business's current confirmed prices.",
};

const quote: QuotePayload = {
  quote_id: "11111111-1111-4111-8111-111111111111",
  line_items: [
    {
      kind: "item",
      item_id: "1",
      label: "Screen repair",
      quantity: 1,
      unit_amount_cents: 8900,
      line_total_cents: 8900,
    },
  ],
  subtotal_cents: 8900,
  tax_cents: 0,
  total_cents: 8900,
  status: "sent",
};

const SHARED_CHROME = [
  "mt-2",
  "w-full",
  "max-w-[520px]",
  "rounded-card",
  "border-hairline",
  "bg-surface",
  "p-4",
];

const SHARED_HEADER = ["text-body", "font-semibold", "text-text"];

function outerClass(html: string): string {
  const match = html.match(/^<div class="([^"]*)"/);
  if (!match) throw new Error(`no outer div class in ${html}`);
  return match[1];
}

function firstHeading(html: string): { className: string; text: string } {
  const match = html.match(/<h3 class="([^"]*)"[^>]*>([^<]*)<\/h3>/);
  if (!match) throw new Error(`no h3 in ${html}`);
  return { className: match[1], text: match[2] };
}

const rendered = {
  Catalog: renderToStaticMarkup(<CatalogCard catalog={catalog} />),
  "Price summary": renderToStaticMarkup(<PriceSummaryCard summary={summary} />),
  Quote: renderToStaticMarkup(<QuoteCard quote={quote} />),
};

describe("RF-9 chat cards share one width and chrome", () => {
  it("renders the identical outer className on all three cards", () => {
    const classes = Object.values(rendered).map(outerClass);
    expect(new Set(classes).size).toBe(1);
  });

  it("carries the shared width and Card chrome on the outer element", () => {
    for (const [name, html] of Object.entries(rendered)) {
      const className = outerClass(html);
      for (const token of SHARED_CHROME) {
        expect(className, `${name} is missing ${token}`).toContain(token);
      }
    }
  });

  it("never renders the retired max-w-[420px] width", () => {
    for (const [name, html] of Object.entries(rendered)) {
      expect(html, `${name} still uses max-w-[420px]`).not.toContain("max-w-[420px]");
    }
  });

  it("gives every card the same h3 header treatment and its own label", () => {
    const labels: Record<string, string> = {
      Catalog: "Current offerings",
      "Price summary": "Price summary",
      Quote: "Quote",
    };
    for (const [name, html] of Object.entries(rendered)) {
      const heading = firstHeading(html);
      for (const token of SHARED_HEADER) {
        expect(heading.className, `${name} heading is missing ${token}`).toContain(token);
      }
      expect(heading.text).toBe(labels[name]);
    }
  });

  it("renders the quote status badge beside the unified header", () => {
    const html = rendered.Quote;
    expect(html).toContain("sent");
    expect(html.indexOf("text-body font-semibold text-text")).toBeLessThan(html.indexOf("sent"));
  });
});
