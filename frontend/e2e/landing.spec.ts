/**
 * E2E browser tests for the bare host (was marketing, now login-in-chat).
 *
 * Surface: tenant-admin (http://localhost:3000 - the bare apex host)
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
    await expect(
      page.getByRole("log", { name: "Onboarding conversation" }),
    ).toBeVisible();
  });

  test("tenant subdomains still resolve to the customer surface", async ({ page }) => {
    await page.goto("http://bytefix.localhost:3000/");
    // The customer surface is the public chat, never the login-in-chat.
    await expect(page.getByPlaceholder("you@example.com")).toHaveCount(0);
  });
});
