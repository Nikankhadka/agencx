/**
 * E2E for E-2: the advanced Wren screens are hidden from the tenant's
 * navigation and from nothing else.
 *
 * Surface: tenant-admin (apex) and platform (/admin)
 *
 * The distinction this pins is the whole ticket. "Hidden" means absent from
 * NAV_ITEMS; it does not mean removed, redirected, or 404'd. Stage 2 re-lands
 * these surfaces with a purpose, and a route that quietly stopped serving in
 * the meantime is a rebuild waiting to happen.
 */

import { test, expect } from "@playwright/test";
import {
  DEMO_USERS,
  loginAsTenantAdmin,
  loginAsPlatformAdmin,
} from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;
const FOUNDER = DEMO_USERS.find((u) => u.surface === "platform")!;

/**
 * The Wren-era operator screens. /dashboards joined this list in E-3: it used
 * to redirect, which made it the one hidden screen that had actually stopped
 * existing - and it holds the eval pass/fail view the keep/pivot/stop signals
 * live in.
 */
const HIDDEN = ["/conversations", "/escalations", "/pricing", "/knowledge", "/dashboards"];

test.describe("advanced screens: hidden, not deleted", () => {

  test("none of them appears in the tenant nav", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    const nav = page.getByRole("navigation", { name: "Console" });
    await expect(nav.getByRole("link")).toHaveText(["Home", "Chats", "Business"]);
    for (const href of HIDDEN) {
      await expect(nav.locator(`a[href="${href}"]`)).toHaveCount(0);
    }
  });

  for (const href of HIDDEN) {
    test(`${href} still serves when typed directly`, async ({ page, request }) => {
      await loginAsTenantAdmin(page, request, BYTEFIX);
      const response = await page.goto(href);

      expect(response?.status(), `${href} must not 404`).toBeLessThan(400);
      await expect(page).toHaveURL(new RegExp(`${href}$`));
      // It renders inside the shell rather than as a bare orphan page.
      await expect(page.getByRole("navigation", { name: "Console" })).toBeVisible();
      // And it is a real screen, not an error boundary.
      await expect(page.getByText(/Application error|something went wrong/i)).toHaveCount(0);
    });
  }
});

test.describe("the platform owner keeps their view", () => {

  test("the all-tenants surface is untouched by the tenant nav re-cut", async ({ page }) => {
    // The helper already lands on "/admin" and waits for the Tenants heading; the
    // point of the test is that the tenant-side re-cut left it alone.
    await loginAsPlatformAdmin(page, FOUNDER);
    await expect(page.getByRole("heading", { name: "Tenants" })).toBeVisible();
  });
});
