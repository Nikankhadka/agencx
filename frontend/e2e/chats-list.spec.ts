/**
 * E2E for the Chats list row (C-6).
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * Scope note: the label itself is pinned deterministically by
 * src/lib/format.test.ts. What e2e is here for is the part unit tests cannot
 * see - that a row with no customer name renders something an owner can point
 * at, and that "needs attention" arrives as a word rather than an unlabelled
 * dot. Both regressed in production precisely because this screen had no e2e
 * coverage at all.
 *
 * The list is stubbed rather than seeded: the seed's conversations all carry
 * customer_ref, so the unnamed case - the only one there is in the live web
 * chat, which never captures a name - never appears in it.
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

const ANONYMOUS_ID = "4f9a2c18-0b7e-4d3a-9c21-77a1b2c3d4e5";

const ROWS = [
  {
    id: ANONYMOUS_ID,
    customer_ref: null,
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
    message_count: 2,
    needs_attention: true,
    pending_summary: "Customer requested the menu items.",
    pending_since: "2026-01-01T00:00:00Z",
    last_activity_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "a1b2c3d4-0b7e-4d3a-9c21-77a1b2c3d4e5",
    customer_ref: "Emma W.",
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
    message_count: 2,
    needs_attention: false,
    last_message: "Thanks, see you Friday.",
    last_activity_at: "2026-01-01T00:00:00Z",
  },
];

test.describe("Chats - telling one row from another", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/conversations", async (route) => {
      await route.fulfill({ json: ROWS });
    });
  });

  test("an unnamed customer is identified by the conversation's short reference", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    const rows = page.getByTestId("chat-row");
    await expect(rows).toHaveCount(2);
    await expect(rows.first()).toContainText("#4F9A2C");
    // A named customer keeps their name and gains no code beside it.
    await expect(rows.nth(1)).toContainText("Emma W.");
    await expect(rows.nth(1)).not.toContainText("#");

    // The reference is searchable, which is what makes it usable for pointing
    // at one conversation among many.
    await page.getByRole("button", { name: "Search conversations" }).click();
    await page.getByTestId("chats-search").fill("4f9a");
    await expect(page.getByTestId("chat-row")).toHaveCount(1);
  });

  test("a row that wants the owner says so in words", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    const badge = page.getByTestId("row-attention");
    await expect(badge).toHaveCount(1);
    await expect(badge).toHaveText("Action needed");
    await expect(page.getByTestId("chat-row").first()).toContainText("Action needed");
  });

  test("the thread header carries the same label as its row", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    await page.getByTestId("chat-row").first().click();
    await page.waitForURL(`**/chats/${ANONYMOUS_ID}`);
    await expect(page.locator("header")).toContainText("#4F9A2C");
  });
});
