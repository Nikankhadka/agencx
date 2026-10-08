/**
 * E2E for RF-14/D38/D43: the Chats queue filters, searches, and pages on the
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
    waiting_on_customer: false,
    ...overrides,
  };
}

function uuid(n: number): string {
  return `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
}

test.describe("RF-14 Chats queue", () => {
  test("opens on Action needed and requests filter=needs_you", async ({ page, request }) => {
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
      row(uuid(5), { resolved_at: "2026-01-02T00:00:00Z" }),
    ]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    await expect(page.getByTestId("chats-filter-count-needs_you")).toHaveText("2");
    await expect(page.getByTestId("chats-filter-count-all")).toHaveText("5");
    await expect(page.getByTestId("chats-filter-count-unread")).toHaveText("1");
    await expect(page.getByTestId("chats-filter-count-resolved")).toHaveText("1");
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
      row(uuid(5), { resolved_at: "2026-01-02T00:00:00Z" }),
    ]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    await page.getByTestId("chats-filter-all").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(5);

    await page.getByTestId("chats-filter-resolved").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(1);
    await expect(page.getByTestId("chat-row").first()).toContainText(
      "Customer 00000000-0000-4000-8000-000000000005",
    );

    await page.getByTestId("chats-filter-unread").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(1);

    expect(urls.some((search) => search.includes("filter=all"))).toBe(true);
    expect(urls.some((search) => search.includes("filter=resolved"))).toBe(true);
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

    const handler = page.getByTestId("row-handler");
    await expect(handler).toHaveCount(1);
    await expect(handler).toHaveText("You");
  });

  test("a waiting row says Waiting on customer and stays out of Action needed", async ({
    page,
    request,
  }) => {
    await mockQueue(page, [
      row(uuid(1), {
        status: "human",
        handler: "human",
        waiting_on_customer: true,
        customer_ref: "Waiting on them",
      }),
      row(uuid(2), { status: "human", handler: "human", customer_ref: "Needs you" }),
    ]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    // Action needed holds the customer-waiting thread, not the waiting one.
    await expect(page.getByTestId("chat-row")).toHaveCount(1);
    await expect(page.getByTestId("chat-row").first()).toContainText("Needs you");

    await page.getByTestId("chats-filter-all").click();
    const waitingRow = page.getByTestId("chat-row").filter({ hasText: "Waiting on them" });
    await expect(waitingRow.getByTestId("row-waiting")).toHaveText("Waiting on customer");
    await expect(waitingRow.getByTestId("row-attention")).toHaveCount(0);
  });

  test("an escalated-and-taken-over row shows both the handler and the badge", async ({
    page,
    request,
  }) => {
    // An open escalation AND a human takeover: two independent axes, so the row
    // must not drop the handler just because the attention badge is present.
    await mockQueue(page, [
      row(uuid(1), {
        needs_attention: true,
        status: "human",
        handler: "human",
        customer_ref: "Escalated and taken over",
      }),
    ]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    const firstRow = page.getByTestId("chat-row").first();
    await expect(firstRow.getByTestId("row-attention")).toHaveCount(1);
    await expect(firstRow.getByTestId("row-handler")).toHaveCount(1);
    await expect(firstRow.getByTestId("row-handler")).toHaveText("You");
  });

  test("a filtered tab pages against the filter-scoped total", async ({ page, request }) => {
    // 60 resolved rows among 80 total: the Resolved total is 60, so the second
    // page appends 10 and Load more stops there rather than against the 80-row
    // dataset.
    const rows = [
      ...Array.from({ length: 60 }, (_, index) =>
        row(uuid(index + 1), { resolved_at: "2026-01-02T00:00:00Z" }),
      ),
      ...Array.from({ length: 20 }, (_, index) => row(uuid(100 + index))),
    ];
    await mockQueue(page, rows);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    await page.getByTestId("chats-filter-resolved").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(50);
    await expect(page.getByTestId("chats-load-more")).toBeVisible();

    await page.getByTestId("chats-load-more").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(60);
    await expect(page.getByTestId("chats-load-more")).toHaveCount(0);
  });
});
