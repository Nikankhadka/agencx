/**
 * E2E for RF-18: real owner read state in the chat queue.
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * The list is route-stubbed so the unread axis is deterministic. Since RF-14
 * the client no longer filters its own page - the tab is a server query - so
 * the stub answers `filter=unread` the way the backend does and returns the
 * envelope.
 */

import { expect, test, type Route } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";
import { countsFor, QUEUE_LIST_URL, type FixtureRow } from "./queue-fixtures";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

const UNREAD_ID = "00000000-0000-4000-8000-000000000001";
const READ_ID = "00000000-0000-4000-8000-000000000002";

function row(overrides: Record<string, unknown>): FixtureRow {
  return {
    id: "00000000-0000-4000-8000-000000000000",
    customer_ref: "Casey",
    status: "closed",
    created_at: "2026-01-01T00:00:00Z",
    message_count: 1,
    needs_attention: false,
    last_message: "A message",
    last_activity_at: "2026-01-01T00:00:00Z",
    unread: false,
    handler: "assistant",
    ...overrides,
  };
}

/** Answer the list the way the backend does: counts over the whole set, items
 * filtered to the requested tab. */
async function fulfillList(route: Route, rows: FixtureRow[]) {
  const filter = new URL(route.request().url()).searchParams.get("filter") ?? "all";
  const items =
    filter === "needs_you"
      ? rows.filter((r) => r.needs_attention || r.status === "human")
      : filter === "human"
        ? rows.filter((r) => r.status === "human")
        : filter === "unread"
          ? rows.filter((r) => r.unread)
          : rows;
  await route.fulfill({ json: { items, total: items.length, counts: countsFor(rows) } });
}

test.describe("Chats - owner read state", () => {
  test("the Unread filter shows only unread conversations, with title emphasis", async ({
    page,
    request,
  }) => {
    await page.route(QUEUE_LIST_URL, async (route) => {
      await fulfillList(route, [
        row({ id: UNREAD_ID, customer_ref: "Unread One", unread: true }),
        row({ id: READ_ID, customer_ref: "Read One", unread: false }),
        row({
          id: "00000000-0000-4000-8000-000000000003",
          customer_ref: "Unread Two",
          unread: true,
        }),
      ]);
    });
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    // The default tab is Needs you; switch to All to exercise the unread
    // emphasis over the full set.
    await page.getByTestId("chats-filter-all").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(3);
    // Unread rows carry the dot; read rows do not.
    await expect(page.getByTestId("row-unread")).toHaveCount(2);

    const unreadTitle = page
      .getByTestId("chat-row")
      .filter({ has: page.getByTestId("row-unread") })
      .first()
      .locator('[data-slot="title"]');
    expect(await unreadTitle.evaluate((el) => getComputedStyle(el).fontWeight)).toBe("600");
    const readTitle = page
      .getByTestId("chat-row")
      .filter({ hasNot: page.getByTestId("row-unread") })
      .first()
      .locator('[data-slot="title"]');
    expect(await readTitle.evaluate((el) => getComputedStyle(el).fontWeight)).toBe("500");

    await page.getByTestId("chats-filter-unread").click();
    await expect(page.getByTestId("chat-row")).toHaveCount(2);
    await expect(page.getByTestId("row-unread")).toHaveCount(2);
  });

  test("opening a conversation clears its unread state in the list", async ({ page, request }) => {
    let unread = true;
    await page.route(QUEUE_LIST_URL, async (route) => {
      await fulfillList(route, [row({ id: UNREAD_ID, customer_ref: "Casey", unread })]);
    });
    await page.route("**/api/conversations/*/read", async (route) => {
      unread = false;
      await route.fulfill({ status: 204, body: "" });
    });
    await page.route("**/api/conversations/*", async (route) => {
      await route.fulfill({
        json: {
          id: UNREAD_ID,
          customer_ref: "Casey",
          customer_email: null,
          channel: "web",
          status: "closed",
          created_at: "2026-01-01T00:00:00Z",
          total_cost_usd: 0,
          messages: [],
        },
      });
    });
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    // The single row is unread and not needs_you, so switch to All to see it.
    await page.getByTestId("chats-filter-all").click();
    await expect(page.getByTestId("row-unread")).toHaveCount(1);

    const read = page.waitForResponse(
      (response) => response.url().includes("/read") && response.request().method() === "POST",
    );
    await page.getByTestId("chat-row").first().click();
    await page.waitForURL(new RegExp(`/chats/${UNREAD_ID}$`));
    await read;
    await page.goBack();

    await expect(page.getByTestId("chats-list")).toBeVisible();
    await expect.poll(() => page.getByTestId("row-unread").count()).toBe(0);
  });
});
