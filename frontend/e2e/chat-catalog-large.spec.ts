/**
 * E2E for ticket 30: the chat catalog's full-list boundary.
 *
 * Surface: customer (http://localhost:3000/{slug}), seeded by `make seed`
 * (bytefix). The turn is scripted through `page.route` so the card renders from
 * a deterministic 96- or 14-offering payload - a live provider cannot emit a
 * specific catalog size on demand.
 *
 * A small menu reads in full. A large one stays bounded at five rows per
 * category and hands the rest to `/{slug}#offerings` in a new tab.
 */

import { expect, test, type Page } from "@playwright/test";

const SLUG = "bytefix";
const CHAT_BUTTON = "Chat with Bytefix Repairs";
const CARD = '[aria-label="Catalog"]';

const sse = (...events: object[]) =>
  events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

function catalogTurn(size: number): string {
  return sse(
    { type: "conversation", conversation_id: "11111111-1111-4111-8111-111111111111" },
    {
      type: "catalog",
      catalog: {
        offerings: Array.from({ length: size }, (_, i) => ({
          id: `item-${i}`,
          name: `Dish ${i}`,
          description: "",
          category: "Plates",
          price_cents: 1000 + i,
        })),
      },
    },
    { type: "token", text: "Here is what we offer." },
    { type: "done" },
  );
}

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

/** Send one mocked turn and wait for the catalog card to settle. */
async function sendCatalogTurn(page: Page, size: number) {
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: catalogTurn(size),
    }),
  );

  // A starter chip drives the send (rf-9 does the same); retry the click and
  // the wait together because `next dev` can briefly hold two copies of the
  // streamed page.
  await expect(async () => {
    await page.getByTestId("starter-0").click();
    await expect(page.locator(CARD)).toHaveCount(1);
  }).toPass({ timeout: 20_000 });
}

test.describe("chat catalog for a large menu", () => {
  test("a 96-offering turn shows the bounded card and the business-page link", async ({ page }) => {
    await openChat(page);
    await sendCatalogTurn(page, 96);

    const card = page.locator(CARD);
    await expect(card.getByText("Dish 4", { exact: true })).toBeVisible();
    await expect(card.getByText("Dish 5", { exact: true })).toHaveCount(0);
    await expect(card.getByText("+91 more", { exact: true })).toBeVisible();

    const link = card.getByRole("link", { name: "View all 96 offerings" });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", `/${SLUG}#offerings`);
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", "noreferrer");

    // The anchor the link lands on is the storefront catalog region.
    await page.goto(`/${SLUG}#offerings`);
    await expect(page.locator("#offerings")).toBeVisible();
  });

  test("a 14-offering turn renders every row, with no overflow line and no link", async ({
    page,
  }) => {
    await openChat(page);
    await sendCatalogTurn(page, 14);

    const card = page.locator(CARD);
    await expect(card.locator("li")).toHaveCount(14);
    await expect(card.getByText("Dish 13", { exact: true })).toBeVisible();
    await expect(card.getByText("more", { exact: false })).toHaveCount(0);
    await expect(card.getByRole("link")).toHaveCount(0);
  });
});
