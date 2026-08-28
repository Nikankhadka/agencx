/**
 * E2E browser tests for tenant-admin login-in-chat (O-2).
 *
 * Surface: tenant-admin (http://localhost:3000)
 * Entry point: /login (reachable from both hosts)
 *
 * Login is now inside the conversation: email -> 6-digit code -> session. The
 * code is GoTrue OTP; the helper reads it out of Mailpit (auth-helpers.ts).
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

test.describe("tenant-admin login-in-chat (app host)", () => {

  for (const user of DEMO_USERS.filter((u) => u.surface === "tenant-admin")) {
    test(`login as ${user.email}`, async ({ page, request }) => {
      await loginAsTenantAdmin(page, request, user);

      // The admin console shell is the post-login destination.
      await expect(page.getByRole("log", { name: "Onboarding conversation" })).toBeVisible();
    });

    test(`signed-in session resumes into the console from /login (${user.email})`, async ({
      page,
      request,
    }) => {
      await loginAsTenantAdmin(page, request, user);

      // A signed-in admin hitting /login is redirected straight into the console.
      await page.goto("/login");
      await page.waitForURL("**/onboarding");
      await expect(page.getByRole("log", { name: "Onboarding conversation" })).toBeVisible();
    });

    test(`sign out returns to the login chat without a reload (${user.email})`, async ({
      page,
      request,
    }) => {
      await loginAsTenantAdmin(page, request, user);

      // The console shell (sidebar) renders the Sign out button on a chrome page.
      await page.goto("/home");
      await page.getByRole("button", { name: "Sign out" }).click();

      // The login chat must render immediately - no manual reload required.
      await expect(page.getByPlaceholder("you@example.com")).toBeVisible();
    });
  }
});

test.describe("tenant-admin login-in-chat (apex)", () => {

  test("the apex redirects to the login chat", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByPlaceholder("you@example.com")).toBeVisible();
  });
});

test.describe("tenant-admin login-in-chat errors", () => {

  test("wrong code shows a calm retry line", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("you@example.com").fill("owner@bytefix.dev");
    await page.getByRole("button", { name: "Send" }).click();
    await page.getByLabel("Digit 1").waitFor();

    for (let i = 0; i < 6; i++) {
      await page.getByLabel(`Digit ${i + 1}`).fill("0");
    }

    // GoTrue's own error (otp_expired) covers both "wrong" and "expired" -
    // it does not distinguish them the way the old backend-issued codes did.
    await expect(
      page.getByText("That code didn't work or expired. Try again, or resend."),
    ).toBeVisible();
  });
});
