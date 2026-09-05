/**
 * E2E for Home and its brief (E-4 / D21).
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * Scope note: the *composition* matrix - which kinds appear for which state,
 * how they are worded and ordered - is covered exhaustively by the unit tests
 * in home/lib/brief.test.ts, against the same function this page calls. What
 * e2e is here to prove is the part unit tests cannot: that the card renders
 * from the real endpoints and its chip lands somewhere real. Creating an
 * unsaved draft through the UI costs a live extract call (see
 * settings-knowledge.spec.ts and its 90s budget), which would buy a slow,
 * provider-dependent test for a case already pinned deterministically.
 */

import { test, expect, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

function waitingConversations(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    customer_ref: `Customer ${index + 1}`,
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
    message_count: 1,
    needs_attention: true,
    pending_summary: "The customer needs a personal response from the owner.",
    pending_since: `2026-01-0${index + 1}T00:00:00Z`,
  }));
}

async function mockConversations(
  page: Page,
  rows: () => ReturnType<typeof waitingConversations>,
  onRequest?: () => void,
) {
  await page.route("**/api/conversations", async (route) => {
    onRequest?.();
    await route.fulfill({ json: rows() });
  });
}

test.describe("Home - the greeting and the brief", () => {

  test("greets the owner and shows who is waiting", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    await expect(page.getByRole("heading", { level: 1 })).toContainText(/Good (morning|afternoon|evening),/);

    // The seed leaves conversations flagged needs_attention, which is the same
    // source the Chats "Action needed" filter reads.
    const waiting = page.getByTestId("waiting-panel");
    await expect(waiting).toBeVisible();
    await expect(waiting).toContainText("waiting for you");
  });

  test("a waiting row opens that conversation directly, not the list", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    await page.getByTestId("waiting-row").first().click();
    await page.waitForURL(/\/chats\/[0-9a-f-]{36}$/);
  });

  test("the waiting panel and the Chats tab badge agree about who is waiting", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    const waitingPanel = page.getByTestId("waiting-panel");
    const chatsTab = page
      .getByRole("navigation", { name: "Console" })
      .getByRole("link", { name: "Chats" });

    // Both read `needs_attention`; if one says someone is waiting, so must the
    // other. Disagreement here is the bug the shared source exists to prevent.
    //
    // Polled, not sampled once: the panel and the badge are fed by two separate
    // queries (Home's and the console layout's), so a bare count() can catch
    // them mid-flight and call a race a disagreement. A real disagreement
    // never converges and still fails here, on timeout.
    await expect
      .poll(async () => {
        const panelShown = await waitingPanel.count();
        const badgeShown = await chatsTab.locator("span[aria-hidden='true']").count();
        return panelShown > 0 === badgeShown > 0;
      })
      .toBe(true);
  });

  test("keeps every waiting row in a phone-sized scroll container", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockConversations(page, () => waitingConversations(4));
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    const rows = page.getByTestId("waiting-panel-rows");
    await expect(rows).toHaveCSS("max-height", "216px");
    await expect(page.getByTestId("waiting-row")).toHaveCount(4);
    await expect(page.getByTestId("waiting-panel-toggle")).toBeVisible();
    await expect
      .poll(async () => rows.evaluate((element) => element.scrollHeight > element.clientHeight))
      .toBe(true);
    await page.getByTestId("waiting-panel-toggle").click();
    await expect(rows).toHaveCSS("max-height", "288px");
  });

  test("uses the larger desktop cap without a toggle for up to five rows", async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await mockConversations(page, () => waitingConversations(5));
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    await expect(page.getByTestId("waiting-panel-rows")).toHaveCSS("max-height", "360px");
    await expect(page.getByTestId("waiting-row")).toHaveCount(5);
    await expect(page.getByTestId("waiting-panel-toggle")).toBeHidden();
  });

  test("keeps the desktop toggle beyond five rows", async ({ page, request }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await mockConversations(page, () => waitingConversations(6));
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    await expect(page.getByTestId("waiting-row")).toHaveCount(6);
    await expect(page.getByTestId("waiting-panel-toggle")).toBeVisible();
    await page.getByTestId("waiting-panel-toggle").click();
    await expect(page.getByTestId("waiting-panel-rows")).toHaveCSS("max-height", "432px");
  });

  test("clears the queue and Chats badge on the four-second refresh", async ({ page, request }) => {
    let resolved = false;
    let requests = 0;
    await mockConversations(
      page,
      () => (resolved ? [] : waitingConversations(1)),
      () => {
        requests += 1;
      },
    );
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    const waitingPanel = page.getByTestId("waiting-panel");
    const chatsTab = page
      .getByRole("navigation", { name: "Console" })
      .getByRole("link", { name: /Chats, 1 waiting/ });
    await expect(waitingPanel).toBeVisible();
    await expect(chatsTab.locator("span[aria-hidden='true']")).toHaveCount(1);

    const initialRequests = requests;
    resolved = true;
    await expect.poll(() => requests, { timeout: 9_000 }).toBeGreaterThan(initialRequests);
    await expect(waitingPanel).toHaveCount(0);
    await expect(chatsTab.locator("span[aria-hidden='true']")).toHaveCount(0);
    await expect(page).toHaveURL(/\/home$/);
  });

  test("Home has no composer - there is no everyday copilot route to answer it", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");
    await expect(page.getByRole("textbox")).toHaveCount(0);
  });
});
