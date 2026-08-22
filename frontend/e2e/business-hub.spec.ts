/**
 * E2E for the Business hub and its Booking page (E-5 / D21).
 *
 * Surface: tenant-admin (http://app.localhost:3000)
 *
 * The hub's shape is the thing under test as much as its contents: Stage 2
 * grows it by adding rows, so "exactly the rows that open onto something" is
 * the invariant worth pinning (PRD, "never build dead surfaces").
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin, tenantAdminHost } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;
const STAGE_2_ROWS = ["Schedule", "Money", "Plan"];

test.describe("Business hub", () => {
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  test("holds only rows that open onto something", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");

    const rows = page.getByRole("main").getByRole("link");
    await expect(rows).toHaveText(["Booking pageWhat customers see, and the link to it", "SettingsWhat your assistant knows"]);

    // Absent, not disabled - the prototype carries them, Stage 1 does not.
    for (const label of STAGE_2_ROWS) {
      await expect(page.getByText(label, { exact: true })).toHaveCount(0);
    }
  });

  test("the booking page shows the business and its public link", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");
    await page.getByRole("link", { name: /Booking page/ }).click();
    await page.waitForURL("**/business/booking");

    await expect(page.getByRole("heading", { level: 2 })).toContainText("Bytefix");

    // Derived from the current host, so it is the address that actually works
    // from this browser - never a hardcoded domain.
    const link = page.getByTestId("booking-link");
    await expect(link).toContainText("bytefix.");
    await expect(link).not.toContainText("http");
    await expect(link).not.toContainText(/\/$/);
  });

  test("copying puts the full URL, scheme and all, on the clipboard", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/booking");

    await page.getByTestId("booking-copy").click();
    await expect(page.getByTestId("booking-copy")).toContainText("Copied");

    const copied = await page.evaluate(() => navigator.clipboard.readText());
    // The pill hides the scheme; what a customer needs is the whole thing.
    expect(copied).toMatch(/^https?:\/\/bytefix\./);
    expect(copied.endsWith("/")).toBe(false);
  });

  test("back from the booking page returns to the hub", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/booking");
    await page.getByRole("button", { name: "Back" }).click();
    await page.waitForURL("**/business");
  });
});
