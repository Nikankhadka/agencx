/**
 * E2E browser tests for the bare host (was marketing, now login-in-chat).
 *
 * Surface: tenant-admin (http://localhost:3000 - the apex)
 *
 * The bare host now renders the login-in-chat surface so business owners land
 * directly in the conversation.
 */

import { test, expect } from "@playwright/test";
import { loginInChat } from "./auth-helpers";

const APEX = "http://localhost:3000";

test.describe("bare host (was marketing, now login-in-chat)", () => {
  test("bare host renders the login chat, not a 404", async ({ page }) => {
    const response = await page.goto(`${APEX}/`);
    expect(response?.status()).toBe(200);
    await expect(page.getByPlaceholder("you@example.com")).toBeVisible();
  });

  test("can log in from the bare host", async ({ page, request }) => {
    await page.goto(`${APEX}/`);
    await loginInChat(page, request, "owner@bytefix.dev");
    // The demo tenant is seeded already-onboarded, so login lands on Home.
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      /Good (morning|afternoon|evening),/,
    );
  });

  test("a tenant slug path resolves to the customer surface", async ({ page }) => {
    await page.goto("/bytefix");
    // The customer surface is the public chat, never the login-in-chat.
    await expect(page.getByPlaceholder("you@example.com")).toHaveCount(0);
  });
});
