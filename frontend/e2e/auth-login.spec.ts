/**
 * E2E browser tests for tenant-admin login-in-chat (O-2).
 *
 * Surface: tenant-admin (http://app.localhost:3000 and bare http://localhost:3000)
 * Entry point: /login (reachable from both hosts)
 *
 * Login is now inside the conversation: email -> 6-digit code -> session. The
 * code is backend-issued and captured (dev-login-code endpoint) for the demo.
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin, tenantAdminHost } from "./auth-helpers";

test.describe("tenant-admin login-in-chat (app host)", () => {
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  for (const user of DEMO_USERS.filter((u) => u.surface === "tenant-admin")) {
    test(`login as ${user.email}`, async ({ page, request }) => {
      await loginAsTenantAdmin(page, request, user);

      // The admin console shell is the post-login destination.
      await expect(page.getByRole("heading", { name: "Onboarding", level: 1 })).toBeVisible();
    });

    test(`signed-in session resumes into the console from /login (${user.email})`, async ({
      page,
      request,
    }) => {
      await loginAsTenantAdmin(page, request, user);

      // A signed-in admin hitting /login is redirected straight into the console.
      await page.goto("/login");
      await page.waitForURL("**/onboarding");
      await expect(page.getByRole("heading", { name: "Onboarding", level: 1 })).toBeVisible();
    });
  }
});

test.describe("tenant-admin login-in-chat (bare host)", () => {
  test.use({ baseURL: "http://localhost:3000" });

  test("bare host renders the login chat (proxy rewrite)", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByPlaceholder("you@example.com")).toBeVisible();
  });
});

test.describe("tenant-admin login-in-chat errors", () => {
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  test("wrong code shows a calm retry line", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("you@example.com").fill("owner@bytefix.dev");
    await page.getByRole("button", { name: "Send" }).click();
    await page.getByLabel("Digit 1").waitFor();

    for (let i = 0; i < 6; i++) {
      await page.getByLabel(`Digit ${i + 1}`).fill("0");
    }

    await expect(
      page.getByText("That code didn't work. Try again, or resend."),
    ).toBeVisible();
  });
});
