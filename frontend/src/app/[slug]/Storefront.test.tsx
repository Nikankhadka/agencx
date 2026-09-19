import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { StorefrontData } from "@/lib/tenant";
import { Storefront } from "./Storefront";

/**
 * M-7: the storefront is a no-image-first composition. These tests pin the
 * states the seed cannot produce on demand - a business with no offerings at
 * all, and the profile-fact vocabulary - through static markup, following the
 * CatalogCard pattern. Row geometry and scroll behavior belong to E2E.
 */

const BASE: StorefrontData = {
  name: "Paws and Claws",
  tagline: null,
  links: {},
  offerings: [],
  has_cover: false,
  cover_url: null,
};

function htmlFor(storefront: StorefrontData): string {
  return renderToStaticMarkup(
    <Storefront slug="paws-and-claws" greeting={null} starterQuestions={[]} storefront={storefront} />,
  );
}

describe("Storefront minimal business", () => {
  it("invites chat instead of declaring an empty catalog", () => {
    const html = htmlFor(BASE);

    expect(html).toContain("Ask me anything");
    expect(html).toContain("Reply");
    expect(html.toLowerCase()).not.toContain("nothing published");
    expect(html).toContain("Powered by Agencx");
  });

  it("shows no offering sections when there is nothing to offer", () => {
    const html = htmlFor(BASE);

    expect(html).not.toContain("What we offer");
    expect(html).not.toContain("offering-price");
  });
});

describe("Storefront hero veil", () => {
  it("renders the veil band in the cover's place when there is no photo", () => {
    const html = htmlFor(BASE);

    expect(html).toContain('data-testid="hero-veil"');
    expect(html).toContain("bg-veil");
    expect(html).not.toContain("<img");
  });

  it("lays the same veil over the photo's lower edge when there is a cover", () => {
    const html = htmlFor({ ...BASE, has_cover: true, cover_url: "https://cdn.example.com/cover.jpg" });

    expect(html).toContain("https://cdn.example.com/cover.jpg");
    expect(html).toContain('data-testid="hero-veil"');
    expect(html).toContain("bottom-0 h-24 bg-veil");
  });
});

describe("Storefront profile facts", () => {
  const FACTS: StorefrontData = {
    ...BASE,
    tagline: "Dog grooming in Newtown · Mon to Sat 9am to 5pm",
    business_type: "Dog grooming",
    hours: "Mon to Sat 9am to 5pm",
    services: ["Dog grooming in Newtown"],
  };

  it("publishes type, hours, and services", () => {
    const html = htmlFor(FACTS);

    expect(html).toContain("Dog grooming");
    expect(html).toContain("Mon to Sat 9am to 5pm");
    expect(html).toContain("Dog grooming in Newtown");
  });

  it("renders services, not the legacy combined tagline, as the subtitle", () => {
    const html = htmlFor(FACTS);

    expect(html).not.toContain("Dog grooming in Newtown · Mon to Sat 9am to 5pm");
  });

  it("lets long fact values wrap instead of clipping them", () => {
    const html = htmlFor({
      ...BASE,
      business_type: "Family-run Middle Eastern restaurant, takeaway and catering",
      hours: "Monday to Friday 11am to 9pm, Saturday 10am to 10pm, closed Sunday",
    });

    // v4 edge case: nothing clipped or ellipsized - the chips wrap.
    expect(html).not.toContain("min-w-0 truncate");
    expect(html).toContain("min-w-0 wrap-anywhere");
  });

  it("renders no subtitle or facts when the profile has none", () => {
    const html = htmlFor({ ...BASE, tagline: null });

    expect(html).not.toContain("offering-price");
    // Only the name heading and the invitation remain - no fact chips.
    expect(html).not.toContain("rounded-chip bg-accent-container");
    expect(html).not.toContain("rounded-chip bg-surface-container");
  });
});

describe("Storefront offerings", () => {
  it("renders the owner's price and omits the price line when there is none", () => {
    const html = htmlFor({
      ...BASE,
      offerings: [
        {
          id: "1",
          name: "Full groom",
          description: "Bath, cut, and nails",
          price_cents: 6500,
          category: null,
          media: null,
        },
        {
          id: "2",
          name: "Nail trim",
          description: "",
          price_cents: null,
          category: null,
          media: null,
        },
      ],
    });

    expect(html).toContain("Full groom");
    expect(html).toContain("$65.00");
    expect(html).toContain("Nail trim");
    expect(html).toContain("What we offer");
    expect(html.match(/offering-price/g) ?? []).toHaveLength(1);
  });
});
