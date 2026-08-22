/**
 * E2E browser tests for the tenant-admin Dashboards route (T-034).
 *
 * Surface: tenant-admin (http://app.localhost:3000)
 * Entry point: /dashboards (after login)
 *
 * Dashboards is temporarily hidden: the nav item is removed and /dashboards
 * redirects to /home (next.config.ts redirects(); E-1 repointed it there when
 * Home became the app's landing tab). This spec asserts the redirect and the
 * absent nav link, and stays ready to restore the original cost/eval render
 * assertions when the feature is re-enabled.
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin, tenantAdminHost } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

test.describe("tenant dashboards (temporarily hidden)", () => {
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  test("/dashboards redirects to /home", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/dashboards");
    await page.waitForURL("**/home");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("Dashboards nav link is absent from the console sidebar", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    // Login lands on /onboarding, which renders chrome-free - assert on a page
    // that still HAS the sidebar, or this passes without proving anything.
    await page.goto("/knowledge");
    await expect(page.getByRole("navigation", { name: "Console" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Dashboards" })).toHaveCount(0);
  });
});
