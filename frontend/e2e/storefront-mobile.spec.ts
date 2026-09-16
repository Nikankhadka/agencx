/**
 * E2E for the M-7 storefront on mobile (runs in the mobile-chrome project).
 *
 * Surface: customer (http://localhost:3000/{slug}), seeded by
 * seed_tenant1_phoneshop - 15 offerings in three categories, zero media, full
 * profile facts. This file covers what only the small viewport shows: the
 * compact no-photo rows, the sticky chip nav with scrollspy, and tap-to-top.
 * The minimal business state (no offerings at all) is pinned in
 * src/app/[slug]/Storefront.test.tsx - the seed cannot produce it.
 */

import { test, expect } from "@playwright/test";
import { expectNoHorizontalOverflow, expectTapTargets } from "./mobile-helpers";

test.describe("the storefront on mobile", () => {
  test("the no-photo base is compact, factual, and tappable", async ({ page }) => {
    await page.goto("/bytefix");

    await expect(page.getByRole("heading", { level: 1 })).toContainText("Bytefix");
    await expect(page.getByText("phone repair shop")).toBeVisible();
    await expect(
      page.getByText(
        "Phone and laptop repairs, screen replacements, battery replacements, data recovery",
      ),
    ).toBeVisible();

    // Text-only rows, no reserved thumbnail space, no horizontal overflow,
    // every control at tap size.
    await expect(page.locator("main img")).toHaveCount(0);
    const row = page.getByRole("button", { name: /iPhone 11 \(Refurbished, 64GB\)/ });
    const box = await row.boundingBox();
    expect(box, "text-only row must not reserve thumbnail space").not.toBeNull();
    expect(box!.height).toBeLessThan(144);
    await expectNoHorizontalOverflow(page);
    await expectTapTargets(page);
  });

  test("the category chips follow the menu", async ({ page }) => {
    await page.goto("/bytefix");

    const nav = page.locator("nav[aria-label='Offer categories']:visible");
    const repairs = nav.getByRole("link", { name: "Repairs" });
    await repairs.click();
    await expect(repairs).toHaveAttribute("aria-current", "true");
    await expect(page.getByRole("heading", { name: "Repairs", exact: true })).toBeInViewport();
  });

  test("the header identity returns to the top", async ({ page }) => {
    await page.goto("/bytefix");

    await page
      .locator("nav[aria-label='Offer categories']:visible")
      .getByRole("link", { name: "Repairs" })
      .click();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);

    await page.getByRole("button", { name: "Back to top" }).click();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  });
});
