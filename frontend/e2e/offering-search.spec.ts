/**
 * E2E for RF-3: offering search on the owner editor and the storefront.
 *
 * Surface: tenant-admin (http://localhost:3000) and the public storefront.
 *
 * Both surfaces load the catalog whole and filter it in memory, so the search
 * is a client interaction. The seeded bytefix catalog has Phones, Accessories
 * and Repairs, which is enough to prove filtering and clearing.
 */

import { expect, test } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

test.describe("RF-3 offering search", () => {
  test("the owner search filters the grouped list and clearing restores it", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/offerings");
    await expect(page.getByTestId("offerings-list")).toBeVisible();

    const before = await page.getByTestId("offering-edit").count();
    expect(before).toBeGreaterThan(3);

    await page.getByTestId("offering-search-toggle").click();
    const input = page.getByTestId("offering-search");
    await expect(input).toBeVisible();

    // A partial name filters to the matching rows.
    await input.fill("iphone");
    await expect(page.getByTestId("offering-edit")).toHaveCount(2);
    await expect(page.getByTestId("offerings-list")).toContainText("iPhone 11");
    await expect(page.getByTestId("offerings-list")).not.toContainText("Screen Repair");

    // A category name matches every member.
    await input.fill("repairs");
    await expect(page.getByTestId("offerings-list")).toContainText("Repairs");
    await expect(page.getByTestId("offerings-list")).toContainText("Battery Replacement");

    // No match shows the empty state.
    await input.fill("zzz-no-such-offering");
    await expect(page.getByTestId("offerings-no-matches")).toBeVisible();
    await expect(page.getByTestId("offerings-list")).toHaveCount(0);

    // Clearing restores every group.
    await input.fill("");
    await expect(page.getByTestId("offering-edit")).toHaveCount(before);
  });

  test("the storefront search filters the catalog and clearing restores it", async ({ page }) => {
    await page.goto("/bytefix");

    // `next dev` streams this page, so the server and client trees can both be
    // in the DOM for a beat; retry the interaction and the assertion together.
    await expect(async () => {
      await page.getByTestId("storefront-search").first().fill("iphone");
      await expect(page.getByTestId("browse-offerings").last()).toContainText("iPhone 11");
    }).toPass({ timeout: 15_000 });
    await expect(page.getByTestId("browse-offerings").last()).not.toContainText("Screen Repair");

    await expect(async () => {
      await page.getByTestId("storefront-search").first().fill("");
      await expect(page.getByTestId("browse-offerings").last()).toContainText("Screen Repair");
    }).toPass({ timeout: 15_000 });
  });
});
