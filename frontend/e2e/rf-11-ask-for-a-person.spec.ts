/**
 * E2E for RF-11: the visible "Ask for a person" control and the deterministic
 * handoff it triggers.
 *
 * Surface: customer (http://localhost:3000/{slug}), seeded by `make seed`
 * (bytefix). Every network call is stubbed through `page.route`: a live
 * provider cannot emit the handoff reply on demand, and the point under test
 * is the client's handling of the control and the stream, not the model's
 * decision to escalate. Follows RF-10's stub patterns, including the query
 * string on the transcript poll.
 *
 * Visual check (performed while writing this spec): at 1024px the control
 * renders as a centered accent pill directly above the composer input, inside
 * the docked complementary panel; at 360px it stays inside the full-height
 * sheet, above the input, at a 44px touch target and remains tappable. It
 * reuses Chip's existing tokens - no raw color, radius, font, or shadow value
 * was introduced.
 */

import { test, expect, type Page } from "@playwright/test";

const SLUG = "bytefix";
const CUSTOMER_URL = `/${SLUG}`;
const CHAT_BUTTON = "Chat with Bytefix Repairs";
const CONVERSATION_ID = "55555555-5555-4555-8555-555555555555";

// The exact deterministic copy the backend streams (escalation.py); the ask is
// appended only when contact is incomplete.
const HANDOFF = "I’ve forwarded your query to the business. They can reply to you here.";
const CONTACT_ASK = "Can I get your name and email so the business can follow up?";

const sse = (...events: object[]) =>
  events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

/** Land on the storefront and open the chat (desktop panel or mobile sheet). */
async function openChat(page: Page) {
  await page.goto(CUSTOMER_URL);
  const panel = page.getByRole("complementary", { name: CHAT_BUTTON });
  const sheet = page.getByRole("dialog", { name: CHAT_BUTTON });
  await expect(async () => {
    await page.getByRole("button", { name: CHAT_BUTTON }).click();
    await expect(panel.or(sheet)).toBeVisible();
  }).toPass({ timeout: 15_000 });
}

/** The incomplete-contact handoff stream: reply + one ask, then the signal. */
async function stubHandoff(page: Page) {
  await page.route("**/api/chat/handoff", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: sse(
        { type: "conversation", conversation_id: CONVERSATION_ID },
        { type: "refusal", text: `${HANDOFF} ${CONTACT_ASK}` },
        { type: "handoff" },
        { type: "done" },
      ),
    }),
  );
}

test.describe("RF-11 Ask for a person (1024px)", () => {
  test.use({ viewport: { width: 1024, height: 900 } });

  test("shows the control and renders the handoff reply without typing", async ({ page }) => {
    await stubHandoff(page);
    await page.route("**/api/chat/*/messages*", (route) =>
      route.fulfill({
        json: [
          {
            id: "66666666-6666-4666-8666-666666666666",
            role: "human_agent",
            content: "A team member will call you shortly.",
            created_at: "2026-10-03T04:00:05Z",
          },
        ],
      }),
    );

    await openChat(page);
    const panel = page.getByRole("complementary", { name: CHAT_BUTTON });
    const control = panel.getByRole("button", { name: "Ask for a person" });
    await expect(control).toBeVisible();

    await control.click();

    // The handoff reply and the one contact ask render as the latest bubble.
    await expect(panel.getByText(/forwarded your query to the business/)).toBeVisible();
    await expect(panel.getByText(/Can I get your name and email/)).toBeVisible();

    // `handoff` started the human-reply poll, which delivers the staff reply.
    await expect(panel.getByText("A team member will call you shortly.")).toBeVisible();

    // Once a handoff is open the control is gone: it cannot be fired twice.
    await expect(panel.getByRole("button", { name: "Ask for a person" })).toHaveCount(0);
  });

  test("fires the handoff exactly once", async ({ page }) => {
    let handoffCalls = 0;
    await page.route("**/api/chat/handoff", (route) => {
      handoffCalls += 1;
      return route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: sse(
          { type: "conversation", conversation_id: CONVERSATION_ID },
          { type: "refusal", text: `${HANDOFF} ${CONTACT_ASK}` },
          { type: "handoff" },
          { type: "done" },
        ),
      });
    });
    await page.route("**/api/chat/*/messages*", (route) => route.fulfill({ json: [] }));

    await openChat(page);
    const control = page.getByRole("button", { name: "Ask for a person" });
    await control.click();
    await expect(page.getByText(/forwarded your query to the business/)).toHaveCount(1);

    // The control is hidden after the handoff, so a second tap is impossible.
    await expect(page.getByRole("button", { name: "Ask for a person" })).toHaveCount(0);
    expect(handoffCalls).toBe(1);
  });
});

test.describe("RF-11 Ask for a person (360px)", () => {
  test.use({ viewport: { width: 360, height: 780 } });

  test("the control is reachable in the mobile sheet and hands off", async ({ page }) => {
    await stubHandoff(page);
    await page.route("**/api/chat/*/messages*", (route) => route.fulfill({ json: [] }));

    await openChat(page);
    const sheet = page.getByRole("dialog", { name: CHAT_BUTTON });
    const control = sheet.getByRole("button", { name: "Ask for a person" });
    await expect(control).toBeVisible();

    await control.click();
    await expect(sheet.getByText(/forwarded your query to the business/)).toBeVisible();
    await expect(sheet.getByRole("button", { name: "Ask for a person" })).toHaveCount(0);
  });
});
