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

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

test.describe("Home - the greeting and the brief", () => {

  test("greets the owner and shows who is waiting", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    await expect(page.getByRole("heading", { level: 1 })).toContainText(/Good (morning|afternoon|evening),/);

    // The seed leaves conversations flagged needs_attention, which is the same
    // source the Chats "Action needed" filter reads.
    const waiting = page.getByTestId("brief-card-waiting");
    await expect(waiting).toBeVisible();
    await expect(waiting).toContainText("waiting on you");
  });

  test("the brief's chip lands on the screen that resolves it", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    await page.getByTestId("brief-card-waiting").getByRole("link", { name: "Open" }).click();
    await page.waitForURL("**/chats");
    await expect(page.getByTestId("chats-filter-action")).toBeVisible();
  });

  test("the brief and the Chats tab dot agree about who is waiting", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/home");

    const waitingCard = page.getByTestId("brief-card-waiting");
    const chatsTab = page
      .getByRole("navigation", { name: "Console" })
      .getByRole("link", { name: "Chats" });

    // Both read `needs_attention`; if one says someone is waiting, so must the
    // other. Disagreement here is the bug the shared source exists to prevent.
    //
    // Polled, not sampled once: the dot and the card are fed by two separate
    // queries (the console layout's and Home's), so a bare count() can catch
    // them mid-flight and call a race a disagreement. A real disagreement
    // never converges and still fails here, on timeout.
    await expect
      .poll(async () => {
        const carded = await waitingCard.count();
        const dotted = await chatsTab.locator("span[aria-hidden='true']").count();
        return carded > 0 === dotted > 0;
      })
      .toBe(true);
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
