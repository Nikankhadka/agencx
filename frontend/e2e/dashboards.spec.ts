/**
 * E2E browser tests for the tenant-admin Dashboards route (T-034).
 *
 * Surface: tenant-admin (http://app.localhost:3000)
 * Entry point: /dashboards (after login)
 *
 * Dashboards is hidden the way every advanced screen is hidden (E-2): absent
 * from the nav, still serving when typed. E-3 removed the redirect that used
 * to stand in for that - the eval pass/fail view is where the keep/pivot/stop
 * signals live, and it has to be reachable to be a signal at all.
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin, tenantAdminHost } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

test.describe("tenant dashboards (unlinked, still serving)", () => {
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  test("/dashboards serves the cost and eval watch", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/dashboards");
    await expect(page).toHaveURL(/\/dashboards$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    // The eval half is the reason this route may not quietly disappear.
    await expect(page.getByText(/eval/i).first()).toBeVisible();
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
