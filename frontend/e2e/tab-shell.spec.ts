/**
 * E2E for the tenant app shell (E-1 / D21): three destinations - Home, Chats,
 * Business - as the sidebar at desktop width, with the advanced Wren screens
 * unlinked but still serving.
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * The mobile half of this ticket (the bottom tab bar at 375px) lives in
 * tab-shell-mobile.spec.ts, which the mobile-chrome project picks up by
 * filename.
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

const HIDDEN_LINKS = ["Conversations", "Escalations", "Pricing", "Dashboards", "Onboarding"];

test.describe("tenant app shell - three destinations", () => {

  test("the sidebar is Home, Chats and Business - and nothing else", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    const nav = page.getByRole("navigation", { name: "Console" });
    await expect(nav).toBeVisible();
    await expect(nav.getByRole("link")).toHaveText(["Home", "Chats", "Business"]);

    for (const label of HIDDEN_LINKS) {
      await expect(nav.getByRole("link", { name: label })).toHaveCount(0);
    }
  });

  test("each tab navigates, and the current one is marked", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    const nav = page.getByRole("navigation", { name: "Console" });
    await expect(nav.getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");

    await nav.getByRole("link", { name: "Chats" }).click();
    await page.waitForURL("**/chats");
    await expect(nav.getByRole("link", { name: "Chats" })).toHaveAttribute("aria-current", "page");

    await nav.getByRole("link", { name: "Business" }).click();
    await page.waitForURL("**/business");
    await expect(nav.getByRole("link", { name: "Business" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("a drill-down keeps its back control and stays under the Business tab", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");

    await page.getByRole("link", { name: /Business details/ }).click();
    await page.waitForURL("**/business/details");

    // The tab is still marked while a screen under it is open.
    const nav = page.getByRole("navigation", { name: "Console" });
    await expect(nav.getByRole("link", { name: "Business" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    await page.getByRole("button", { name: "Back" }).click();
    await page.waitForURL("**/business");
  });

  test("a tab destination has no back control", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");
    await expect(page.getByRole("button", { name: "Back" })).toHaveCount(0);
  });

  // The advanced screens' own posture - unlinked but still serving - is E-2's,
  // and lives in hidden-screens.spec.ts.
});
