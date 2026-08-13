/**
 * E2E browser tests for the tenant-admin Dashboards route (T-034).
 *
 * Surface: tenant-admin (http://app.localhost:3000)
 * Entry point: /dashboards (after login)
 *
 * Dashboards is temporarily hidden: the nav item is removed and /dashboards
 * redirects to /onboarding (next.config.ts redirects()). This spec asserts the
 * redirect and the absent nav link, and stays ready to restore the original
 * cost/eval render assertions when the feature is re-enabled.
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin, tenantAdminHost } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

test.describe("tenant dashboards (temporarily hidden)", () => {
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  test("/dashboards redirects to /onboarding", async ({ page }) => {
    await loginAsTenantAdmin(page, BYTEFIX);
    await page.goto("/dashboards");
    await page.waitForURL("**/onboarding");
    await expect(page.getByRole("heading", { name: "Onboarding", level: 1 })).toBeVisible();
  });

  test("Dashboards nav link is absent from the console sidebar", async ({ page }) => {
    await loginAsTenantAdmin(page, BYTEFIX);
    await expect(page.getByRole("link", { name: "Dashboards" })).toHaveCount(0);
  });
});
