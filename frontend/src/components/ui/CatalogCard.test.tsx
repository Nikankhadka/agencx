import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CatalogCard, type CatalogPayload, type CatalogOffering } from "./CatalogCard";

/**
 * W-9: the offering id (`catalog_id=` in the model's prompt, `id` on this
 * payload - backend/app/services/context_package.py, backend/app/agents/
 * agent_node.py's show_catalog handler) is how a later turn names a row, so
 * it has to be on the payload. CatalogCard only ever reads it for `key=`,
 * never prints it - these tests pin that split.
 *
 * Ticket 30: the card reads the whole catalog for a small menu and stays
 * bounded above 20, where it hands the rest off to `/{slug}#offerings`.
 */
const SLUG = "bytefix";

function offer(id: string, name: string, overrides: Partial<CatalogOffering> = {}): CatalogOffering {
  return {
    id,
    name,
    description: "",
    category: null,
    price_cents: null,
    ...overrides,
  };
}

function catalogOf(offerings: CatalogOffering[]): CatalogPayload {
  return { offerings };
}

describe("CatalogCard", () => {
  it("shows 'Price not listed' for an offering with no price", () => {
    const catalog: CatalogPayload = {
      offerings: [offer("8f14e45f-ceea-467e-bd3d-46f5b2f6e242", "Custom engraving")],
    };

    const html = renderToStaticMarkup(<CatalogCard catalog={catalog} slug={SLUG} />);

    expect(html).toContain("Price not listed");
  });

  it("never lets an offering id reach the rendered output", () => {
    const id = "8f14e45f-ceea-467e-bd3d-46f5b2f6e242";
    const catalog: CatalogPayload = {
      offerings: [
        offer(id, "Coffee", {
          description: "Freshly brewed",
          category: "Drinks",
          price_cents: 350,
        }),
      ],
    };

    const html = renderToStaticMarkup(<CatalogCard catalog={catalog} slug={SLUG} />);

    expect(html).not.toContain(id);
  });

  it("renders the server-provided price cents verbatim, no arithmetic", () => {
    // An odd amount that would look wrong under any rounding or unit
    // conversion the component might be tempted to do on its own.
    const catalog: CatalogPayload = {
      offerings: [offer("1", "Odd amount", { price_cents: 12345 })],
    };

    const html = renderToStaticMarkup(<CatalogCard catalog={catalog} slug={SLUG} />);

    expect(html).toContain("$123.45");
  });

  it("shows pricing wording verbatim when there is no fixed price", () => {
    const catalog: CatalogPayload = {
      offerings: [offer("1", "Catering box", { pricing_wording: "from $12 a head" })],
    };

    const html = renderToStaticMarkup(<CatalogCard catalog={catalog} slug={SLUG} />);

    expect(html).toContain("from $12 a head");
    expect(html).not.toContain("Price not listed");
  });

  it("renders a wording-only offering as words, never a formatted amount", () => {
    const catalog: CatalogPayload = {
      offerings: [offer("1", "Catering box", { category: "Events", pricing_wording: "market price" })],
    };

    const html = renderToStaticMarkup(<CatalogCard catalog={catalog} slug={SLUG} />);

    expect(html).toContain("market price");
    expect(html).not.toContain("$");
    expect(html).not.toContain("Price not listed");
  });

  it("groups an offering under every confirmed category", () => {
    const catalog: CatalogPayload = {
      offerings: [
        offer("repair", "Screen replacement", {
          category: "Repairs",
          categories: [
            { id: "repairs", name: "Repairs", position: 0, is_primary: true },
            { id: "screens", name: "Screen care", position: 1, is_primary: false },
          ],
          price_cents: 9900,
        }),
      ],
    };

    const html = renderToStaticMarkup(<CatalogCard catalog={catalog} slug={SLUG} />);

    expect(html).toContain("Repairs");
    expect(html).toContain("Screen care");
    expect(html.match(/Screen replacement/g) ?? []).toHaveLength(2);
  });

  it("renders all 14 offerings with no overflow line and no page link", () => {
    const offerings = Array.from({ length: 14 }, (_, i) =>
      offer(`item-${i}`, `Dish ${i}`, { category: "Plates", price_cents: 1000 + i }),
    );

    const html = renderToStaticMarkup(
      <CatalogCard catalog={catalogOf(offerings)} slug={SLUG} />,
    );

    expect(html.match(/Dish \d+/g) ?? []).toHaveLength(14);
    expect(html).toContain("Dish 13");
    expect(html).not.toContain("more");
    expect(html).not.toContain("View all");
    expect(html).not.toContain("#offerings");
  });

  it("bounds a 96-offering catalog and links to the business page", () => {
    const offerings = Array.from({ length: 96 }, (_, i) =>
      offer(`item-${i}`, `Dish ${i}`, { category: "Plates", price_cents: 1000 + i }),
    );

    const html = renderToStaticMarkup(
      <CatalogCard catalog={catalogOf(offerings)} slug={SLUG} />,
    );

    expect(html).toContain("Dish 4");
    expect(html).not.toContain("Dish 5");
    expect(html).toContain("+91 more");
    expect(html).toContain("View all 96 offerings");
    expect(html).toContain('href="/bytefix#offerings"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noreferrer"');
  });

  it("renders at most 5 rows per category for a 200-offering payload", () => {
    const offerings = ["Repairs", "Phones", "Cases", "Audio"].flatMap((category) =>
      Array.from({ length: 50 }, (_, i) =>
        offer(`${category}-${i}`, `${category} item ${i}`, {
          category,
          price_cents: 1000 + i,
        }),
      ),
    );

    const html = renderToStaticMarkup(
      <CatalogCard catalog={catalogOf(offerings)} slug={SLUG} />,
    );

    expect(html.match(/<li/g) ?? []).toHaveLength(20);
    expect(html.match(/\+45 more/g) ?? []).toHaveLength(4);
    expect(html).toContain("View all 200 offerings");
  });

  it("caps a large category and says how many more there are", () => {
    // 24 is the smallest catalog above the 20-offering full-list boundary.
    const offerings = Array.from({ length: 24 }, (_, i) =>
      offer(`item-${i}`, `Dish ${i}`, { category: "Plates", price_cents: 1000 + i }),
    );

    const html = renderToStaticMarkup(
      <CatalogCard catalog={catalogOf(offerings)} slug={SLUG} />,
    );

    expect(html).toContain("Dish 4");
    expect(html).not.toContain("Dish 5");
    expect(html).toContain("+19 more");
  });

  it("shows no overflow line when a small category fits", () => {
    const offerings = Array.from({ length: 5 }, (_, i) =>
      offer(`item-${i}`, `Dish ${i}`, { category: "Plates", price_cents: 1000 }),
    );

    const html = renderToStaticMarkup(
      <CatalogCard catalog={catalogOf(offerings)} slug={SLUG} />,
    );

    expect(html).not.toContain("more");
  });
});
