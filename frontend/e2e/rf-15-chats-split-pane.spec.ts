/**
 * E2E for RF-15: the desktop split-pane Chats surface.
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * `lg+` is one split view - the queue list left, the conversation thread right -
 * and selecting a row must not navigate the list away. Below `lg` the old
 * list-then-thread returns, with the console's bottom tab bar standing over it,
 * and `/chats/[id]` stays a deep link into either shape.
 *
 * The test project is Desktop Chrome at 1280x720; the two acceptance viewports
 * are set explicitly so the `lg` boundary (1024px) is the thing under test, not
 * the runner's default. The list is route-stubbed with `mockQueue`, and the
 * detail route is stubbed the way chats-read-state.spec.ts stubs it, so the
 * thread is deterministic without a live model. Panes are addressed by their
 * stable testids and asserted with `toBeVisible` / `toBeHidden`, so a pane that
 * is mounted but display-none (the mobile case) reads as hidden.
 */

import { expect, test, type Page, type Route } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";
import { mockQueue, type FixtureRow } from "./queue-fixtures";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

const CASEY_ID = "00000000-0000-4000-8000-0000000000c1";
const RILEY_ID = "00000000-0000-4000-8000-0000000000c2";
const CASEY_LABEL = "Casey";
const CUSTOMER_MESSAGE = "Where is my phone?";

const ROWS: FixtureRow[] = [
  {
    id: CASEY_ID,
    customer_ref: CASEY_LABEL,
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
    message_count: 2,
    needs_attention: true,
    pending_summary: "Casey asked about their repair.",
    pending_since: "2026-01-01T00:00:00Z",
    last_activity_at: "2026-01-01T00:00:00Z",
    handler: "assistant",
  },
  {
    id: RILEY_ID,
    customer_ref: "Riley",
    status: "closed",
    created_at: "2026-01-01T00:00:00Z",
    message_count: 2,
    needs_attention: false,
    last_message: "Thanks, all sorted.",
    last_activity_at: "2026-01-01T00:00:00Z",
    handler: "assistant",
  },
];

/** Stub the thread detail and its read marker, so the right pane renders a
 * named customer with one message and no live backend call. */
async function stubThread(page: Page, id: string, customerRef: string) {
  await page.route(`**/api/conversations/${id}`, async (route: Route) => {
    await route.fulfill({
      json: {
        id,
        customer_ref: customerRef,
        customer_email: null,
        channel: "web",
        status: "open",
        created_at: "2026-01-01T00:00:00Z",
        total_cost_usd: 0,
        messages: [
          {
            id: "00000000-0000-4000-8000-0000000000d1",
            role: "customer",
            content: CUSTOMER_MESSAGE,
            agent_node: null,
            created_at: "2026-01-01T00:00:00Z",
            metadata: {},
            cost_usd: null,
            tool_calls: [],
          },
        ],
      },
    });
  });
  await page.route(`**/api/conversations/${id}/read`, async (route: Route) => {
    await route.fulfill({ status: 204, body: "" });
  });
}

test.describe("RF-15 - desktop split-pane Chats, mobile navigation preserved", () => {
  test.beforeEach(async ({ page, request }) => {
    await mockQueue(page, ROWS);
    await stubThread(page, CASEY_ID, CASEY_LABEL);
    await loginAsTenantAdmin(page, request, BYTEFIX);
  });

  test("at 1024 the list stays and the thread opens beside it", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 800 });
    await page.goto("/chats");

    // The left pane owns the queue; the right pane holds the placeholder.
    await expect(page.getByTestId("chats-list-pane")).toBeVisible();
    await expect(page.getByTestId("chats-list")).toBeVisible();
    await expect(page.getByTestId("chats-empty-pane")).toBeVisible();

    // Switch to All so both fixture rows are in the list.
    await page.getByTestId("chats-filter-all").click();
    const listRows = page.getByTestId("chats-list-pane").getByTestId("chat-row");
    await expect(listRows).toHaveCount(2);

    await listRows.first().click();
    await page.waitForURL(`**/chats/${CASEY_ID}`);

    // The URL moved but the list did not: same pane, same rows still mounted.
    await expect(page.getByTestId("chats-list")).toBeVisible();
    await expect(page.getByTestId("chats-list-pane").getByTestId("chat-row")).toHaveCount(2);
    // The thread opened on the right, headed by the customer's label.
    const thread = page.getByTestId("chats-thread-pane");
    await expect(thread.locator("header")).toContainText(CASEY_LABEL);
    await expect(thread.getByText(CUSTOMER_MESSAGE)).toBeVisible();
  });

  test("/chats/<id> deep-links to the same split state", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 800 });
    await page.goto(`/chats/${CASEY_ID}`);

    // Both panes are present from a cold load, not only after a row click.
    await expect(page.getByTestId("chats-list-pane")).toBeVisible();
    await expect(page.getByTestId("chats-list")).toBeVisible();
    await expect(page.getByTestId("chats-list-pane").getByTestId("chat-row")).toHaveCount(1);
    const thread = page.getByTestId("chats-thread-pane");
    await expect(thread).toBeVisible();
    await expect(thread.locator("header")).toContainText(CASEY_LABEL);
  });

  test("at 360 a row opens the full-height thread with the bar, and back returns", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 360, height: 740 });
    await page.goto("/chats");

    await expect(page.getByTestId("chats-list-pane")).toBeVisible();
    await expect(page.getByTestId("chats-thread-pane")).toBeHidden();

    await page.getByTestId("chats-list-pane").getByTestId("chat-row").first().click();
    await page.waitForURL(`**/chats/${CASEY_ID}`);

    // The list is gone, the thread fills the frame, and the bar stays over it.
    await expect(page.getByTestId("chats-list-pane")).toBeHidden();
    await expect(page.getByTestId("chats-thread-pane")).toBeVisible();
    await expect(page.locator('nav[aria-label="Main"]')).toBeVisible();
    await expect(page.getByTestId("chats-thread-pane").locator("header")).toContainText(CASEY_LABEL);

    await page.goBack();
    await expect(page).toHaveURL(/\/chats$/);
    await expect(page.getByTestId("chats-list-pane")).toBeVisible();
    await expect(page.getByTestId("chats-thread-pane")).toBeHidden();
  });

  test("browser back at 1024 returns to the list and the placeholder", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 800 });
    await page.goto("/chats");
    await page.getByTestId("chats-filter-all").click();
    await page.getByTestId("chats-list-pane").getByTestId("chat-row").first().click();
    await page.waitForURL(`**/chats/${CASEY_ID}`);
    await expect(page.getByTestId("chats-thread-pane").locator("header")).toContainText(CASEY_LABEL);

    await page.goBack();
    await expect(page).toHaveURL(/\/chats$/);
    await expect(page.getByTestId("chats-list-pane")).toBeVisible();
    // No thread selected: the right pane shows the empty placeholder again.
    await expect(page.getByTestId("chats-empty-pane")).toBeVisible();
  });
});
