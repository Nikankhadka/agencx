/**
 * E2E browser tests for tenant-admin login.
 *
 * Surface: tenant-admin (http://app.localhost:3000 and bare http://localhost:3000)
 * Entry point: /login (reachable from both hosts)
 *
 * T-004: successful login redirects into the admin console shell at
 * /onboarding; a signed-in user visiting /login resumes straight into it.
 */

import { test, expect } from "@playwright/test";
import {
  DEMO_USERS,
  loginAsTenantAdmin,
  submitLoginForm,
  tenantAdminHost,
} from "./auth-helpers";

test.describe("tenant-admin login (app host)", () => {
  // Tenant-admin login uses the app.localhost host.
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  for (const user of DEMO_USERS.filter((u) => u.surface === "tenant-admin")) {
    test(`login as ${user.email}`, async ({ page }) => {
      await loginAsTenantAdmin(page, user);

      // The admin console shell is the post-login destination.
      await expect(page.getByRole("heading", { name: "Onboarding", level: 1 })).toBeVisible();
    });

    test(`signed-in session resumes into the console from /login (${user.email})`, async ({ page }) => {
      await loginAsTenantAdmin(page, user);

      // A signed-in admin hitting /login is redirected straight into the console.
      await page.goto("/login");
      await page.waitForURL("**/onboarding");
      await expect(page.getByRole("heading", { name: "Onboarding", level: 1 })).toBeVisible();
    });
  }
});

test.describe("tenant-admin login (bare host)", () => {
  // The bare host (localhost:3000) now renders the login page too.
  test.use({ baseURL: "http://localhost:3000" });

  test("bare host renders the login page (proxy rewrite)", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();

    await submitLoginForm(page, "owner@bytefix.dev", "wren-demo");
    await page.waitForURL("**/onboarding");
    await expect(
      page.getByRole("heading", { name: "Onboarding", level: 1 }),
    ).toBeVisible();
  });
});

test.describe("tenant-admin login errors", () => {
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  test("wrong password shows error", async ({ page }) => {
    await page.goto("/login");
    await submitLoginForm(page, "owner@bytefix.dev", "wrong-password");

    // The supabase-js error message should appear on the password input's error
    // label (the Input component renders error text below the field).
    // We wait for any error text to appear rather than asserting a specific
    // message since GoTrue messages may vary. .first() disambiguates the
    // inline error (p.text-danger) from the identical toast message.
    await expect(page.locator("p.text-danger", { hasText: "Invalid login credentials" }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("missing email shows HTML5 validation", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Log in" }).click();

    // The browser's built-in form validation should prevent submission.
    // Playwright can assert the input is invalid.
    const emailInput = page.getByLabel("Email");
    await expect(emailInput).toHaveAttribute("required", "");
  });
});
