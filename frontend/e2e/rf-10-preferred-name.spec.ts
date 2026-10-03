/**
 * E2E for RF-10: the preferred-name chip and same-tab refresh restoration.
 *
 * Surface: customer (http://localhost:3000/{slug}), seeded by `make seed`
 * (bytefix). Every turn is scripted through `page.route` - a live provider
 * cannot emit a `contact` event on demand, and the point under test is the
 * client's handling of the event, not the model's decision to ask.
 *
 * Covers: no chip before any name; a chip after a `contact` event; a second turn
 * changing the name; and a reload that keeps the chip and restores the text
 * transcript from the public messages endpoint. Cards, composer draft, and the
 * handoff banner stay RF-12 and are not asserted here.
 */

import { test, expect, type Page } from "@playwright/test";

const SLUG = "bytefix";
const CUSTOMER_URL = `/${SLUG}`;
const CHAT_BUTTON = "Chat with Bytefix Repairs";
const CONVERSATION_ID = "11111111-1111-4111-8111-111111111111";

const sse = (...events: object[]) =>
  events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

/** Land on the storefront and open the docked desktop chat panel (RF-8). */
async function openChat(page: Page) {
  await page.goto(CUSTOMER_URL);
  await expect(async () => {
    await page.getByRole("button", { name: CHAT_BUTTON }).click();
    await expect(page.getByRole("complementary", { name: CHAT_BUTTON })).toBeVisible();
  }).toPass({ timeout: 15_000 });
}

/** Send one turn, retrying the fill and click together (typing-indicator.spec). */
async function ask(page: Page, question = "What do you charge for a screen?") {
  await expect(async () => {
    const box = page.getByLabel("Message");
    await expect(box).toHaveCount(1);
    await box.fill(question);
  }).toPass({ timeout: 15_000 });
  await page.getByRole("button", { name: "Send" }).click();
}

test("no name chip appears before a contact event", async ({ page }) => {
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: sse(
        { type: "conversation", conversation_id: CONVERSATION_ID },
        { type: "token", text: "A screen repair is $129." },
        { type: "done" },
      ),
    }),
  );

  await openChat(page);
  await ask(page);
  await expect(page.getByText("A screen repair is $129.")).toBeVisible();
  await expect(page.getByTestId("customer-name-chip")).toHaveCount(0);
});

test("the chip shows the name a contact event carries", async ({ page }) => {
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: sse(
        { type: "conversation", conversation_id: CONVERSATION_ID },
        { type: "contact", name: "Sam" },
        { type: "token", text: "Hi Sam, what can I help with?" },
        { type: "done" },
      ),
    }),
  );

  await openChat(page);
  await ask(page);
  const chip = page.getByTestId("customer-name-chip");
  await expect(chip).toContainText("Sam");
  // check:tokens cannot catch a class that does not exist (memory, C-6), so pin
  // that the semantic tokens actually resolved: teal-m text on the accent wash.
  await expect(chip).toHaveCSS("color", "rgb(0, 122, 127)");
  await expect(chip).toHaveCSS("background-color", "rgba(255, 56, 92, 0.07)");
});

test("a second turn corrects the name on the chip", async ({ page }) => {
  let turn = 0;
  await page.route("**/api/chat", (route) => {
    turn += 1;
    const name = turn === 1 ? "Sam" : "Alex";
    return route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: sse(
        { type: "conversation", conversation_id: CONVERSATION_ID },
        { type: "contact", name },
        { type: "token", text: `Hi ${name}.` },
        { type: "done" },
      ),
    });
  });

  await openChat(page);
  await ask(page, "It's Sam");
  await expect(page.getByTestId("customer-name-chip")).toContainText("Sam");
  await ask(page, "Actually, call me Alex");
  await expect(page.getByTestId("customer-name-chip")).toContainText("Alex");
  await expect(page.getByTestId("customer-name-chip")).not.toContainText("Sam");
});

test("a reload keeps the chip and restores the transcript", async ({ page }) => {
  await page.route("**/api/chat/*/messages*", (route) =>
    route.fulfill({
      json: [
        {
          id: "22222222-2222-4222-8222-222222222222",
          role: "customer",
          content: "hello",
          created_at: "2026-10-03T04:00:00Z",
        },
        {
          id: "33333333-3333-4333-8333-333333333333",
          role: "assistant",
          content: "Hi Sam, what can I help with?",
          created_at: "2026-10-03T04:00:01Z",
        },
      ],
    }),
  );
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: sse(
        { type: "conversation", conversation_id: CONVERSATION_ID },
        { type: "contact", name: "Sam" },
        { type: "token", text: "Hi Sam, what can I help with?" },
        { type: "done" },
      ),
    }),
  );

  await openChat(page);
  await ask(page, "hello");
  await expect(page.getByTestId("customer-name-chip")).toContainText("Sam");

  await page.reload();
  await openChat(page);

  // The chip survives, and the transcript is restored from the messages API
  // rather than left as the opening greeting over a stored name.
  await expect(page.getByTestId("customer-name-chip")).toContainText("Sam");
  await expect(page.getByText("Hi Sam, what can I help with?")).toBeVisible();
  await expect(page.getByText("hello", { exact: true })).toBeVisible();
});
