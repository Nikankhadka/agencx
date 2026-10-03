/**
 * E2E for RF-12: same-tab refresh restoration of content, cards, and state.
 *
 * Surface: customer (http://localhost:3000/{slug}), seeded by `make seed`
 * (bytefix). Every network call is stubbed through `page.route`: a live
 * provider cannot emit a specific card on demand, and the point under test is
 * the client's restore behaviour, not the model's decision. Follows RF-10/RF-11
 * patterns exactly, including the `**` + query string on the transcript glob.
 *
 * Covers: cards restore from `metadata.response`; an unsent draft restores (and
 * a draft-only refresh keeps the opening state); a handoff restores and the
 * human-reply poll resumes; an escalated banner restores and locks the composer.
 */

import { test, expect, type Page } from "@playwright/test";

const SLUG = "bytefix";
const CUSTOMER_URL = `/${SLUG}`;
const CHAT_BUTTON = "Chat with Bytefix Repairs";
const CONVERSATION_ID = "11111111-1111-4111-8111-111111111111";

const sse = (...events: object[]) =>
  events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

/** The card payloads the backend persists into `metadata.response`. */
const PRICE_SUMMARY = {
  line_items: [
    {
      kind: "item",
      item_id: "33333333-3333-4333-8333-333333333333",
      label: "Tempered glass protector",
      quantity: 1,
      unit_amount_cents: 1500,
      line_total_cents: 1500,
    },
  ],
  subtotal_cents: 1500,
  tax_cents: 150,
  total_cents: 1650,
  disclaimer: "Prices are estimates.",
};

const QUOTE = {
  quote_id: "44444444-4444-4444-8444-444444444444",
  line_items: [
    {
      kind: "rule",
      code: "screen-repair-a",
      label: "Screen repair (tier A)",
      quantity: 1,
      unit_amount_cents: 12000,
      line_total_cents: 12000,
    },
  ],
  subtotal_cents: 12000,
  tax_cents: 960,
  total_cents: 12960,
  status: "sent",
};

const CATALOG = {
  offerings: [
    {
      id: "55555555-5555-4555-8555-555555555555",
      name: "Tempered glass protector",
      description: "A protective layer",
      category: null,
      price_cents: 1500,
    },
  ],
};

/** Land on the storefront and open the docked desktop chat panel (RF-8). */
async function openChat(page: Page) {
  await page.goto(CUSTOMER_URL);
  await expect(async () => {
    await page.getByRole("button", { name: CHAT_BUTTON }).click();
    await expect(page.getByRole("complementary", { name: CHAT_BUTTON })).toBeVisible();
  }).toPass({ timeout: 15_000 });
}

/** Send one turn, retrying the fill and click together. */
async function ask(page: Page, question: string) {
  await expect(async () => {
    const box = page.getByLabel("Message");
    await expect(box).toHaveCount(1);
    await box.fill(question);
  }).toPass({ timeout: 15_000 });
  await page.getByRole("button", { name: "Send" }).click();
}

/** A plain text turn that also mints and stores the conversation id. */
function stubPlainTurn(page: Page) {
  return page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: sse(
        { type: "conversation", conversation_id: CONVERSATION_ID },
        { type: "token", text: "Sure, here is the answer." },
        { type: "done" },
      ),
    }),
  );
}

test.describe("RF-12 same-tab refresh restore", () => {
  test("cards restore from the customer-safe response payload", async ({ page }) => {
    await stubPlainTurn(page);
    // The stored transcript carries each assistant turn's persisted card. Cards
    // are restored from `response` alone - never the owner-only metadata blob.
    await page.route("**/api/chat/*/messages*", (route) =>
      route.fulfill({
        json: [
          {
            id: "60000000-0000-4000-8000-000000000001",
            role: "customer",
            content: "what do you charge?",
            created_at: "2026-10-03T04:00:00Z",
          },
          {
            id: "60000000-0000-4000-8000-000000000002",
            role: "assistant",
            content: "Here is a price summary.",
            created_at: "2026-10-03T04:00:01Z",
            response: { type: "price_summary", summary: PRICE_SUMMARY },
          },
          {
            id: "60000000-0000-4000-8000-000000000003",
            role: "assistant",
            content: "Here is your quote.",
            created_at: "2026-10-03T04:00:02Z",
            response: { type: "quote", quote: QUOTE },
          },
          {
            id: "60000000-0000-4000-8000-000000000004",
            role: "assistant",
            content: "Here is what we offer.",
            created_at: "2026-10-03T04:00:03Z",
            response: { type: "catalog", catalog: CATALOG },
          },
        ],
      }),
    );

    await openChat(page);
    await ask(page, "what do you charge?");
    await expect(page.getByText("Sure, here is the answer.")).toBeVisible();

    await page.reload();
    await openChat(page);
    const panel = page.getByRole("complementary", { name: CHAT_BUTTON });

    const priceSummary = panel.getByLabel("Price summary");
    await expect(priceSummary).toBeVisible();
    await expect(priceSummary.getByText("$16.50")).toBeVisible();

    const quote = panel.getByLabel("Quote");
    await expect(quote).toBeVisible();
    await expect(quote.getByText("$129.60")).toBeVisible();

    const catalog = panel.getByLabel("Catalog");
    await expect(catalog).toBeVisible();
    await expect(catalog.getByText("Tempered glass protector")).toBeVisible();
    await expect(catalog.getByText("$15.00")).toBeVisible();
  });

  test("an unsent draft restores and the opening state remains without a conversation", async ({
    page,
  }) => {
    await openChat(page);
    const panel = page.getByRole("complementary", { name: CHAT_BUTTON });
    await panel.getByLabel("Message").fill("half a question");
    // No send: no conversation id is stored, so a refresh must restore the
    // draft over the opening greeting and starters.
    await expect(panel.getByLabel("Message")).toHaveValue("half a question");

    await page.reload();
    await openChat(page);
    const restored = page.getByRole("complementary", { name: CHAT_BUTTON });
    await expect(restored.getByLabel("Message")).toHaveValue("half a question");
    await expect(restored.getByText(/How can I help today\?/)).toBeVisible();
  });

  test("a handoff restores and the human-reply poll resumes", async ({ page }) => {
    const HANDOFF = "I've forwarded your query to the business. They can reply to you here.";
    await page.route("**/api/chat/handoff", (route) =>
      route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: sse(
          { type: "conversation", conversation_id: CONVERSATION_ID },
          { type: "refusal", text: HANDOFF },
          { type: "handoff" },
          { type: "done" },
        ),
      }),
    );
    await page.route("**/api/chat/*/messages*", (route) =>
      route.fulfill({
        json: [
          {
            id: "70000000-0000-4000-8000-000000000001",
            role: "assistant",
            content: HANDOFF,
            created_at: "2026-10-03T04:00:01Z",
          },
          {
            id: "70000000-0000-4000-8000-000000000002",
            role: "human_agent",
            content: "A team member will call you shortly.",
            created_at: "2026-10-03T04:00:02Z",
          },
        ],
      }),
    );

    await openChat(page);
    const control = page.getByRole("button", { name: "Ask for a person" });
    await control.click();
    await expect(page.getByText(/forwarded your query to the business/)).toBeVisible();

    await page.reload();
    await openChat(page);
    const panel = page.getByRole("complementary", { name: CHAT_BUTTON });

    // handoffSeen restored: the control stays hidden and the poll delivers the
    // human reply with no further action.
    await expect(panel.getByRole("button", { name: "Ask for a person" })).toHaveCount(0);
    await expect(panel.getByText("A team member will call you shortly.")).toBeVisible();
  });

  test("an escalated banner restores and the composer stays locked", async ({ page }) => {
    await page.route("**/api/chat", (route) =>
      route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: sse(
          { type: "conversation", conversation_id: CONVERSATION_ID },
          { type: "refusal", text: "I've passed this to the team." },
          { type: "escalated" },
          { type: "done" },
        ),
      }),
    );
    await page.route("**/api/chat/*/messages*", (route) =>
      route.fulfill({
        json: [
          {
            id: "80000000-0000-4000-8000-000000000001",
            role: "assistant",
            content: "I've passed this to the team.",
            created_at: "2026-10-03T04:00:01Z",
          },
        ],
      }),
    );

    await openChat(page);
    await ask(page, "someone please help");
    const banner = page.getByText("Someone from the business will take it from here.");
    await expect(banner).toBeVisible();
    await expect(page.getByLabel("Message")).toHaveCount(0);

    await page.reload();
    await openChat(page);
    await expect(
      page.getByText("Someone from the business will take it from here."),
    ).toBeVisible();
    await expect(page.getByLabel("Message")).toHaveCount(0);
  });
});
