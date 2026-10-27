import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CatalogCard, type CatalogPayload } from "./CatalogCard";
import { PriceSummaryCard, type PriceSummaryPayload } from "./PriceSummaryCard";
import { StructuredResponse } from "./StructuredResponse";

const SLUG = "bytefix";

/**
 * W-9 box 4 (slice 1.3): the owner's transcript views
 * (`(tenant-admin)/(console)/chats/[id]/page.tsx` and
 * `.../conversations/[id]/page.tsx`) restore a persisted `messages.metadata.
 * response` payload by handing it straight to this component, which is also
 * what the live customer surface renders inline for the same event. Parity
 * holds only if this dispatcher renders the exact same markup as the card
 * component would given that payload's inner field directly - these tests
 * pin that, plus the "nothing for anything else" half of the contract.
 *
 * Ticket 30: the tenant slug is a prop, not a payload field, so the restored
 * card keeps working. The owner detail payload carries no slug, so an owner
 * transcript gets the bounded card without the page link.
 */
describe("StructuredResponse", () => {
  it("renders a persisted price_summary payload identically to PriceSummaryCard", () => {
    const summary: PriceSummaryPayload = {
      line_items: [
        {
          kind: "item",
          item_id: "8f14e45f-ceea-467e-bd3d-46f5b2f6e242",
          label: "Screen repair",
          quantity: 2,
          unit_amount_cents: 8900,
          line_total_cents: 17800,
        },
      ],
      subtotal_cents: 17800,
      tax_cents: 0,
      total_cents: 17800,
      disclaimer: "Based on the business's current confirmed prices.",
    };
    const response = { type: "price_summary", summary };

    const viaDispatch = renderToStaticMarkup(<StructuredResponse response={response} />);
    const viaCardDirectly = renderToStaticMarkup(<PriceSummaryCard summary={summary} />);

    expect(viaDispatch).toBe(viaCardDirectly);
  });

  it("renders a persisted catalog payload identically to CatalogCard", () => {
    const catalog: CatalogPayload = {
      offerings: [
        {
          id: "1",
          name: "Custom engraving",
          description: "",
          category: null,
          price_cents: null,
        },
        {
          id: "2",
          name: "Battery replacement",
          description: "Genuine part, 1yr warranty",
          category: "Repairs",
          price_cents: 6000,
        },
      ],
    };
    const response = { type: "catalog", catalog };

    const viaDispatch = renderToStaticMarkup(
      <StructuredResponse response={response} slug={SLUG} />,
    );
    const viaCardDirectly = renderToStaticMarkup(
      <CatalogCard catalog={catalog} slug={SLUG} />,
    );

    expect(viaDispatch).toBe(viaCardDirectly);
  });

  it("carries the catalog page link through when a slug is known", () => {
    const catalog: CatalogPayload = {
      offerings: Array.from({ length: 24 }, (_, i) => ({
        id: `item-${i}`,
        name: `Dish ${i}`,
        description: "",
        category: "Plates",
        price_cents: 1000,
      })),
    };

    const html = renderToStaticMarkup(
      <StructuredResponse response={{ type: "catalog", catalog }} slug={SLUG} />,
    );

    expect(html).toContain("View all 24 offerings");
    expect(html).toContain('href="/bytefix#offerings"');
  });

  it("renders a bounded catalog without a link when no slug is available", () => {
    const catalog: CatalogPayload = {
      offerings: Array.from({ length: 24 }, (_, i) => ({
        id: `item-${i}`,
        name: `Dish ${i}`,
        description: "",
        category: "Plates",
        price_cents: 1000,
      })),
    };

    const html = renderToStaticMarkup(<StructuredResponse response={{ type: "catalog", catalog }} />);

    expect(html).toContain("Dish 4");
    expect(html).toContain("+19 more");
    expect(html).not.toContain("View all");
  });

  it("renders nothing for an unknown response type", () => {
    const html = renderToStaticMarkup(
      <StructuredResponse response={{ type: "refusal", text: "no" }} />,
    );
    expect(html).toBe("");
  });

  it("renders nothing for a malformed response - not an object, or missing type", () => {
    expect(renderToStaticMarkup(<StructuredResponse response={null} />)).toBe("");
    expect(renderToStaticMarkup(<StructuredResponse response={undefined} />)).toBe("");
    expect(renderToStaticMarkup(<StructuredResponse response="price_summary" />)).toBe("");
    expect(renderToStaticMarkup(<StructuredResponse response={{}} />)).toBe("");
  });
});
