/**
 * E2E for RF-13: failed-send recovery and draft preservation.
 *
 * Surface: customer (http://localhost:3000/{slug}), seeded by `make seed`
 * (bytefix). Follows the RF-12 pattern exactly - open the docked complementary
 * panel, stub every network call through `page.route`.
 *
 * Covers both failure paths the ticket names: a network failure (fetch rejects)
 * and an in-stream `error` event. Each must keep the exact payload in the
 * composer, carry an inline Retry on the failed bubble, never replay on its own,
 * and - on the explicit retry - post the exact original text once and recover
 * the same bubble in place (no duplicate customer bubble).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const SLUG = "bytefix";
const CUSTOMER_URL = `/${SLUG}`;
const CHAT_BUTTON = "Chat with Bytefix Repairs";
const CONVERSATION_ID = "13131313-1313-4131-8131-131313131313";
const QUESTION = "Do you fix cracked screens?";
const REPLY = "Yes, we repair cracked screens in about an hour.";

const sse = (...events: object[]) =>
  events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

const TURN = sse(
  { type: "conversation", conversation_id: CONVERSATION_ID },
  { type: "token", text: REPLY },
  { type: "done" },
);

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

/** The failure-then-success route both tests share: the first POST fails (in a
 * way the test chooses), the second answers. Returns a live view of the posts. */
function stubFailThenSucceed(
  page: Page,
  firstAttempt: (route: Route) => Promise<void>,
): { posts: () => number; bodies: () => Array<Record<string, unknown>> } {
  let posts = 0;
  const bodies: Array<Record<string, unknown>> = [];
  void page.route("**/api/chat", async (route) => {
    posts += 1;
    bodies.push(JSON.parse(route.request().postData() ?? "{}"));
    if (posts === 1) {
      await firstAttempt(route);
      return;
    }
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: TURN,
    });
  });
  return { posts: () => posts, bodies: () => bodies };
}

test.describe("RF-13 failed-send recovery", () => {
  test("a network failure keeps the draft and retries the exact payload in place", async ({
    page,
  }) => {
    const stub = stubFailThenSucceed(page, (route) => route.abort("failed"));

    await openChat(page);
    await ask(page, QUESTION);

    const composer = page.getByLabel("Message");
    await expect(composer).toHaveValue(QUESTION);
    const retry = page.getByRole("button", { name: "Retry" });
    await expect(retry).toBeVisible();

    // No automatic replay: a beat later the failed turn still has not posted.
    await page.waitForTimeout(1000);
    expect(stub.posts()).toBe(1);
    // The customer's message appears exactly once - the failure did not append
    // a duplicate bubble.
    await expect(page.getByText(QUESTION, { exact: true })).toHaveCount(1);

    await retry.click();

    await expect(page.getByText(REPLY)).toBeVisible();
    await expect(composer).toHaveValue("");
    await expect(retry).toHaveCount(0);
    expect(stub.posts()).toBe(2);
    expect(stub.bodies()[1]?.message).toBe(QUESTION);
    // The retry recovered the same bubble in place: still one customer bubble.
    await expect(page.getByText(QUESTION, { exact: true })).toHaveCount(1);
  });

  test("an in-stream error event also keeps the draft and retries the exact payload", async ({
    page,
  }) => {
    const stub = stubFailThenSucceed(page, (route) =>
      route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream" },
        body: sse(
          { type: "conversation", conversation_id: CONVERSATION_ID },
          {
            type: "error",
            code: "internal_error",
            detail: "Something went wrong on my side - please send that again.",
            request_id: "req-rf-13",
          },
        ),
      }),
    );

    await openChat(page);
    await ask(page, QUESTION);

    const composer = page.getByLabel("Message");
    await expect(composer).toHaveValue(QUESTION);
    const retry = page.getByRole("button", { name: "Retry" });
    await expect(retry).toBeVisible();

    await page.waitForTimeout(1000);
    expect(stub.posts()).toBe(1);
    await expect(page.getByText(QUESTION, { exact: true })).toHaveCount(1);

    await retry.click();

    await expect(page.getByText(REPLY)).toBeVisible();
    await expect(composer).toHaveValue("");
    await expect(retry).toHaveCount(0);
    expect(stub.posts()).toBe(2);
    expect(stub.bodies()[1]?.message).toBe(QUESTION);
    await expect(page.getByText(QUESTION, { exact: true })).toHaveCount(1);
  });
});
