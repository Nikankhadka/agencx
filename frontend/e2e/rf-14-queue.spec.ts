/**
 * E2E for RF-14/D38: the Chats queue filters, searches, and pages on the
 * server over the complete tenant dataset.
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * The list is route-stubbed and filter-aware: the stub reads `filter`, `q`,
 * and `offset` off the request the way the backend does, so the assertions
 * prove the *client* sends the right query and renders what comes back - the
 * server side is pinned by backend/tests/test_conversations_api.py. Playwright
 * globs do not match a query string, so the list route is `?*` and is
 * registered before the `/conversations/:id` route.
 *
 * The pure URL and waiting-time logic is unit-tested in
 * chats/lib/queue.test.ts; this covers the browser behaviour.
 */

import { expect, test } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";
import { mockQueue, type FixtureRow } from "./queue-fixtures";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

type Row = FixtureRow;

function row(id: string, overrides: Partial<Row> = {}): Row {
  return {
    id,
    customer_ref: `Customer ${id}`,
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
    message_count: 1,
    needs_attention: false,
    unread: false,
    last_message: "A message",
    last_activity_at: "2026-01-01T00:00:00Z",
    handler: "assistant",
    ...overrides,
  };
}

function uuid(n: number): string {
  return `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
}

test.describe("RF-14 Chats queue", () => {
  test("opens on Needs you and requests filter=needs_you", async ({ page, request }) => {
    const urls = await mockQueue(page, [
      row(uuid(1), { needs_attention: true, pending_summary: "Wants a price" }),
      row(uuid(2)),
    ]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    await expect(page.getByTestId("chats-filter-needs_you")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("chat-row")).toHaveCount(1);
    expect(urls.some((search) => search.includes("filter=needs_you"))).toBe(true);
  });

  test("renders each tab's count from the envelope", async ({ page, request }) => {
    await mockQueue(page, [
      row(uuid(1), { needs_attention: true }),
      row(uuid(2), { unread: true }),
      row(uuid(3), { status: "human", handler: "human" }),
      row(uuid(4)),
    ]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    await expect(page.getByTestId("chats-filter-count-needs_you")).toHaveText("2");
    await expect(page.getByTestId("chats-filter-count-all")).toHaveText("4");
    await expect(page.getByTestId("chats-filter-count-unread")).toHaveText("1");
    await expect(page.getByTestId("chats-filter-count-human")).toHaveText("1");
  });

  test("switching tabs sends the right filter and shows only its rows", async ({
    page,
    request,
  }) => {
    const urls = await mockQueue(page, [
      row(uuid(1), { needs_attention: true }),
      row(uuid(2), { unread: true }),
      row(uuid(3), { status: "human", handler: "human" }),
      row(uuid(4)),
    ]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    await page.getByTestId("chats-filter-all").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(4);

    await page.getByTestId("chats-filter-human").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(1);
    await expect(page.getByTestId("chat-row").first()).toContainText("Customer 00000000-0000-4000-8000-000000000003");

    await page.getByTestId("chats-filter-unread").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(1);

    expect(urls.some((search) => search.includes("filter=all"))).toBe(true);
    expect(urls.some((search) => search.includes("filter=human"))).toBe(true);
    expect(urls.some((search) => search.includes("filter=unread"))).toBe(true);
  });

  test("search sends q and matches across the whole dataset, not just the page", async ({
    page,
    request,
  }) => {
    const rows = Array.from({ length: 120 }, (_, index) => row(uuid(index + 1)));
    // A name that sits well past the first 50-row page.
    rows[110] = row(uuid(111), { customer_ref: "Farhan the Far One" });
    const urls = await mockQueue(page, rows);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    // Search runs under the active tab; switch to All so the match, which is
    // not needs_you, is in scope.
    await page.getByTestId("chats-filter-all").click();
    await page.getByRole("button", { name: "Search conversations" }).click();
    await page.getByTestId("chats-search").fill("Farhan");

    await expect(page.getByTestId("chat-row")).toHaveCount(1);
    await expect(page.getByTestId("chat-row").first()).toContainText("Farhan the Far One");
    await expect
      .poll(() => urls.some((search) => search.includes("q=Farhan")))
      .toBe(true);
  });

  test("Load more appends the second page and disappears at the total", async ({ page, request }) => {
    const rows = Array.from({ length: 75 }, (_, index) => row(uuid(index + 1)));
    await mockQueue(page, rows);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    await page.getByTestId("chats-filter-all").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(50);
    await expect(page.getByTestId("chats-load-more")).toBeVisible();

    await page.getByTestId("chats-load-more").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(75);
    // 75 loaded of a total of 75: nothing more to load, so the button is gone.
    await expect(page.getByTestId("chats-load-more")).toHaveCount(0);
  });

  test("a human-handled row shows its handler as You", async ({ page, request }) => {
    await mockQueue(page, [
      row(uuid(1), { status: "human", handler: "human", customer_ref: "Taken over" }),
    ]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    await page.getByTestId("chats-filter-human").click();
    const handler = page.getByTestId("row-handler");
    await expect(handler).toHaveCount(1);
    await expect(handler).toHaveText("You");
  });
});
