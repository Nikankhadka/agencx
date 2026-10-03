/**
 * E2E for RF-9: the offering, price-summary, and quote cards share one width
 * and chrome.
 *
 * Surface: customer (http://localhost:3000/{slug}), seeded by `make seed`
 * (bytefix). The turn is scripted through `page.route` so all three cards render
 * from one deterministic mocked assistant turn - a live provider cannot emit
 * quote + price-summary + catalog on demand.
 *
 * The check runs at the two widths RF-9 names: 360px (the mobile modal sheet)
 * and 1024px (the docked desktop panel, RF-8).
 */

import { expect, test, type Page } from "@playwright/test";

const SLUG = "bytefix";
const CHAT_BUTTON = "Chat with Bytefix Repairs";

const CARD_SELECTORS = {
  Catalog: '[aria-label="Catalog"]',
  "Price summary": '[aria-label="Price summary"]',
  Quote: '[aria-label="Quote"]',
} as const;

const sse = (...events: object[]) =>
  events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

const LINE_ITEM = {
  kind: "item",
  item_id: "1",
  label: "Screen repair",
  quantity: 1,
  unit_amount_cents: 8900,
  line_total_cents: 8900,
};

const CARD_TURN = sse(
  { type: "conversation", conversation_id: "11111111-1111-4111-8111-111111111111" },
  {
    type: "quote",
    quote: {
      quote_id: "11111111-1111-4111-8111-111111111111",
      line_items: [LINE_ITEM],
      subtotal_cents: 8900,
      tax_cents: 0,
      total_cents: 8900,
      status: "sent",
    },
  },
  {
    type: "price_summary",
    summary: {
      line_items: [LINE_ITEM],
      subtotal_cents: 8900,
      tax_cents: 0,
      total_cents: 8900,
      disclaimer: "Based on the business's current confirmed prices.",
    },
  },
  {
    type: "catalog",
    catalog: {
      offerings: [
        {
          id: "1",
          name: "Screen repair",
          description: "Genuine part",
          category: "Repairs",
          price_cents: 8900,
        },
      ],
    },
  },
  { type: "token", text: "Here is your quote." },
  { type: "done" },
);

/** next dev streams the page; retry the open until the chat host is live. */
async function openChat(page: Page) {
  const panel = page.getByRole("complementary", { name: CHAT_BUTTON });
  const sheet = page.getByRole("dialog", { name: CHAT_BUTTON });
  await page.goto(`/${SLUG}`);
  await expect(async () => {
    await page.getByRole("button", { name: CHAT_BUTTON }).click();
    await expect(panel.or(sheet)).toBeVisible();
  }).toPass({ timeout: 15_000 });
}

/** Send one mocked turn and wait for all three cards to settle to one copy each. */
async function renderCards(page: Page) {
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: CARD_TURN,
    }),
  );

  // A starter chip drives the send; seeded for bytefix (rf-8 does the same).
  // The click and the wait are retried together because `next dev` can briefly
  // hold two copies of the streamed page (typing-indicator.spec.ts::ask).
  await expect(async () => {
    await page.getByTestId("starter-0").click();
    for (const selector of Object.values(CARD_SELECTORS)) {
      await expect(page.locator(selector)).toHaveCount(1);
    }
  }).toPass({ timeout: 20_000 });
}

/** Assert the three cards align on width, left edge, and shared chrome. */
async function assertAligned(page: Page) {
  await expect(async () => {
    const styles: Array<{ maxWidth: string; padding: string; borderRadius: string }> = [];
    const boxes: Array<{ x: number; width: number }> = [];

    for (const selector of Object.values(CARD_SELECTORS)) {
      const card = page.locator(selector);
      await expect(card).toHaveCount(1);
      const box = await card.boundingBox();
      expect(box, `${selector} has no bounding box`).not.toBeNull();
      boxes.push({ x: box!.x, width: box!.width });
      styles.push(
        await card.evaluate((node) => {
          const computed = getComputedStyle(node);
          return {
            maxWidth: computed.maxWidth,
            padding: computed.padding,
            borderRadius: computed.borderRadius,
          };
        }),
      );
    }

    const widths = boxes.map((b) => b.width);
    const xs = boxes.map((b) => b.x);
    expect(Math.max(...widths) - Math.min(...widths)).toBeLessThanOrEqual(1);
    expect(Math.max(...xs) - Math.min(...xs)).toBeLessThanOrEqual(1);

    for (const style of styles) {
      expect(style.maxWidth).toBe("520px");
      expect(style.padding).toBe(styles[0].padding);
      expect(style.borderRadius).toBe(styles[0].borderRadius);
    }
  }).toPass({ timeout: 15_000 });
}

test.describe("RF-9 card alignment at 360px", () => {
  test.use({ viewport: { width: 360, height: 780 } });

  test("offering, price-summary, and quote cards share one width and chrome", async ({ page }) => {
    await openChat(page);
    await renderCards(page);
    await assertAligned(page);
  });
});

test.describe("RF-9 card alignment at 1024px", () => {
  test.use({ viewport: { width: 1024, height: 900 } });

  test("offering, price-summary, and quote cards share one width and chrome", async ({ page }) => {
    await openChat(page);
    await renderCards(page);
    await assertAligned(page);
  });
});
