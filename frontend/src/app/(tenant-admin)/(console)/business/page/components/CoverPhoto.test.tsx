import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { CoverPhoto, downscale } from "./CoverPhoto";

/**
 * The repo's vitest setup is the node environment with server rendering only -
 * there is no DOM, no @testing-library, and no jsdom, and the ticket forbids a
 * new dependency. So these pin the cover's rendered states and the decode
 * fallback; the interactive PUT/DELETE/recovery flow is covered end to end in
 * frontend/e2e/business-hub.spec.ts.
 */
function cover(hasCover: boolean) {
  return renderToStaticMarkup(
    <CoverPhoto hasCover={hasCover} onChanged={() => {}} />,
  );
}

describe("CoverPhoto", () => {
  it("invites a photo while empty and offers no removal", () => {
    const html = cover(false);
    expect(html).toContain('data-testid="booking-cover"');
    expect(html).toContain('data-testid="booking-cover-input"');
    expect(html).toContain("Tap to add a cover photo");
    expect(html).not.toContain('data-testid="booking-cover-remove"');
  });

  it("offers the explicit remove affordance while a cover is loading", () => {
    // Server rendering runs no effects, so `src` is still null here: this pins
    // the loading state (has_cover true, bytes not yet fetched), where the
    // remove control must already be offered.
    const html = cover(true);
    expect(html).toContain('data-testid="booking-cover-remove"');
    expect(html).toContain('aria-label="Change cover photo"');
  });

  it("returns the original file when the browser cannot decode it", async () => {
    const file = new File(["bytes"], "cover.jpg", { type: "image/jpeg" });
    // Node has no createImageBitmap; the fallback hands the bytes to the
    // server's own cap rather than dropping the pick.
    expect(typeof createImageBitmap).toBe("undefined");
    await expect(downscale(file)).resolves.toBe(file);
  });
});
