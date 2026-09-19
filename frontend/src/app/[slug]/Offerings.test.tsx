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
