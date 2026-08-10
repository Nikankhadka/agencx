/**
 * E2E browser tests for the bare host (was marketing, now login).
 *
 * Surface: tenant-admin (http://localhost:3000 - the bare apex host)
 *
 * The bare host now renders the business login page so business owners
 * land directly on the login form.
 */

import { test, expect } from "@playwright/test";
import { submitLoginForm } from "./auth-helpers";

const APEX = "http://localhost:3000";

test.describe("bare host (was marketing, now login)", () => {
  test("bare host renders the login page, not a 404", async ({ page }) => {
    const response = await page.goto(`${APEX}/`);
    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { name: "Log in" }),
    ).toBeVisible();
  });

  test("bare host login page links to signup", async ({ page }) => {
    await page.goto(`${APEX}/`);
    await expect(
      page.getByRole("link", { name: "Create your business" }),
    ).toBeVisible();
  });

  test("can log in from the bare host", async ({ page }) => {
    await page.goto(`${APEX}/`);
    await submitLoginForm(page, "owner@bytefix.dev", "wren-demo");
    await page.waitForURL("**/onboarding");
    await expect(
      page.getByRole("heading", { name: "Onboarding", level: 1 }),
    ).toBeVisible();
  });

  test("tenant subdomains still resolve to the customer surface", async ({ page }) => {
    await page.goto("http://bytefix.localhost:3000/");
    await expect(
      page.getByRole("heading", { name: "Log in" }),
    ).toHaveCount(0);
  });
});
