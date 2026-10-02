import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { StorefrontOffering } from "@/lib/tenant";
import { Offerings } from "./Offerings";

/**
 * M-7 US-4: row media has three branches - image, video with a poster, and
 * video with none - and none of them were exercised by Storefront.test.tsx,
 * which only ever passes `media: null`. These pin the static markup for each,
 * following the CatalogCard/Storefront pattern. The onError fallback tiles
 * need a real DOM event and aren't covered here - see Offerings.tsx's own
 * `RowMedia` for that behavior.
 */

function offering(overrides: Partial<StorefrontOffering>): StorefrontOffering {
  return {
    id: "1",
    name: "Item",
    description: "",
    price_cents: null,
    category: null,
    media: null,
    ...overrides,
  };
}

function htmlFor(item: StorefrontOffering): string {
  return renderToStaticMarkup(<Offerings offerings={[item]} onSelect={() => {}} />);
}

function catalogHtml(items: StorefrontOffering[]): string {
  return renderToStaticMarkup(<Offerings offerings={items} onSelect={() => {}} />);
}

describe("Offerings row media", () => {
  it("renders an image thumbnail when media is a photo", () => {
    const html = htmlFor(
      offering({
        media: { type: "image", provider: "cloudinary", url: "https://cdn.example.com/photo.jpg" },
      }),
    );

    expect(html).toContain('src="https://cdn.example.com/photo.jpg"');
    expect(html).not.toContain("Video");
  });

  it("renders the poster and a Video badge when a video has a poster", () => {
    const html = htmlFor(
      offering({
        media: {
          type: "video",
          provider: "cloudinary",
          url: "https://cdn.example.com/clip.mp4",
          poster_url: "https://cdn.example.com/poster.jpg",
        },
      }),
    );

    expect(html).toContain('src="https://cdn.example.com/poster.jpg"');
    expect(html).toContain("Video");
  });

  it("renders the placeholder tile with no image when a video has no poster", () => {
    const html = htmlFor(
      offering({
        media: { type: "video", provider: "youtube", url: "https://youtu.be/x", poster_url: null },
      }),
    );

    expect(html).not.toContain("<img");
    expect(html).toContain("Video");
  });

  it("reserves no media space when there is none", () => {
    const html = htmlFor(offering({}));

    expect(html).not.toContain("<img");
    expect(html).not.toContain("Video");
  });
});

describe("Offerings catalog density", () => {
  it("uses one compact region and no category navigation for up to six offerings", () => {
    const html = catalogHtml([
      offering({ id: "1", name: "Coffee", category: "Breakfast / Drinks" }),
      offering({ id: "2", name: "Coke", category: "Drinks", price_cents: 250 }),
      offering({ id: "3", name: "Salads" }),
      offering({ id: "4", name: "Fresh juice" }),
    ]);

    expect(html).toContain('data-testid="compact-offerings"');
    expect(html).toContain("What we offer");
    expect(html).toContain("Breakfast / Drinks");
    expect(html).toContain("Drinks");
    expect(html).toContain("More");
    expect(html).not.toContain('aria-label="Offer categories"');
    expect(html).not.toContain(">Browse<");
  });

  it("keeps category navigation for a mature catalog starting at seven offerings", () => {
    const html = catalogHtml(
      Array.from({ length: 7 }, (_, index) =>
        offering({
          id: String(index + 1),
          name: `Item ${index + 1}`,
          category: index < 4 ? "Repairs" : "Phones",
        }),
      ),
    );

    expect(html).toContain('data-testid="browse-offerings"');
    expect(html).toContain('aria-label="Offer categories"');
    expect(html).toContain(">Browse<");
    expect(html).not.toContain('data-testid="compact-offerings"');
  });

  it("does not repeat a category label when a compact catalog has only one group", () => {
    const html = catalogHtml([
      offering({ id: "1", name: "Coffee" }),
      offering({ id: "2", name: "Tea" }),
    ]);

    expect(html.match(/What we offer/g) ?? []).toHaveLength(1);
    expect(html).not.toContain(">More<");
  });

  it("keeps two distinct offerings with the same price as two rows", () => {
    // RF-3: grouping is by category and identity, never by price - two
    // offerings that happen to cost the same must not collapse into one row.
    const html = catalogHtml([
      offering({ id: "a", name: "Screen replacement", price_cents: 5000, category: "Repairs" }),
      offering({ id: "b", name: "Battery replacement", price_cents: 5000, category: "Repairs" }),
    ]);

    expect(html.match(/Screen replacement/g) ?? []).toHaveLength(1);
    expect(html.match(/Battery replacement/g) ?? []).toHaveLength(1);
  });

  it("renders pricing wording verbatim when there is no fixed price", () => {
    const html = htmlFor(
      offering({ name: "Catering box", price_cents: null, pricing_wording: "from $12 a head" }),
    );

    expect(html).toContain("from $12 a head");
  });

  it("formats a fixed price through money.ts", () => {
    const html = htmlFor(offering({ name: "Widget", price_cents: 12345 }));

    // money.ts's Intl formatting, not inline arithmetic.
    expect(html).toContain("$123.45");
  });

  it("renders a category with a single member", () => {
    const html = catalogHtml([
      offering({ id: "a", name: "Solo item", category: "Only category" }),
      offering({ id: "b", name: "Other item", category: "Second category" }),
    ]);

    expect(html).toContain("Only category");
    expect(html).toContain("Solo item");
  });

  it("shows one offering once on each confirmed category shelf", () => {
    const html = catalogHtml([
      offering({
        id: "repair",
        name: "Screen replacement",
        category: "Repairs",
        categories: [
          { id: "repairs", name: "Repairs", position: 0, is_primary: true },
          { id: "screens", name: "Screen care", position: 1, is_primary: false },
        ],
      }),
      offering({ id: "case", name: "Phone case", category: "Accessories" }),
    ]);

    expect(html).toContain("Repairs");
    expect(html).toContain("Screen care");
    expect(html).toContain("Accessories");
    expect(html.match(/Screen replacement/g) ?? []).toHaveLength(2);
  });
});
