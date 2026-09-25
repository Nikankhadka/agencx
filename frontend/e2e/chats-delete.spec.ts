import { expect, test, type APIRequestContext } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SLUG = "bytefix";

/**
 * T-029 (D35): the owner deletes one customer conversation from its thread.
 *
 * The delete is real, end to end. The quoted-conversation refusal is stubbed:
 * reaching a real quote needs the assistant to build one, which a free-tier
 * provider will not do deterministically. The 409 itself is proven against
 * Postgres in backend/tests/test_conversations_api.py; this spec proves the
 * screen shows the server's reason and leaves the thread alone.
 */
async function customerConversation(request: APIRequestContext) {
  const opened = await request.post(`${API_URL}/api/chat`, {
    data: { slug: SLUG, message: "Please delete this test conversation." },
  });
  expect(opened.ok()).toBeTruthy();
  const id = /"conversation_id": ?"([0-9a-f-]{36})"/.exec(await opened.text())?.[1];
  expect(id).toBeTruthy();
  return id as string;
}

test("the owner deletes a conversation and it leaves the list", async ({ page, request }) => {
  const id = await customerConversation(request);
  const ref = `#${id.replace(/-/g, "").slice(0, 6).toUpperCase()}`;

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  await page.goto("/chats");
  // Opened through the list, not by URL, so the list checked afterwards is the
  // client-side one - a full page load would refetch it and prove nothing.
  await page.getByTestId("chat-row").filter({ hasText: ref }).click();
  await page.waitForURL(`**/chats/${id}`);
  await expect(page.getByText("Please delete this test conversation.")).toBeVisible();

  await page.getByTestId("delete-conversation").click();
  await expect(page.getByText("Delete this conversation?")).toBeVisible();
  await page.getByTestId("confirm-accept").click();

  await page.waitForURL("**/chats");
  await expect(page.getByText("Conversation deleted")).toBeVisible();
  await expect(page.getByTestId("chat-row").filter({ hasText: ref })).toHaveCount(0);

  // Gone on the server too, not just hidden by the client.
  await page.goto(`/chats/${id}`);
  await expect(page.getByText("conversation not found")).toBeVisible();
});

test("a conversation the server refuses to delete stays, with the reason shown", async ({
  page,
  request,
}) => {
  const id = await customerConversation(request);
  const reason =
    "This conversation has a quote attached and cannot be deleted here. Quotes are kept as records - ask us in writing to remove it.";
  await page.route(`**/api/conversations/${id}`, async (route) => {
    if (route.request().method() !== "DELETE") return route.fallback();
    await route.fulfill({
      status: 409,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "about:blank",
        title: "Conflict",
        status: 409,
        detail: reason,
        code: "conflict",
      }),
    });
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  await page.goto(`/chats/${id}`);
  await page.getByTestId("delete-conversation").click();
  await page.getByTestId("confirm-accept").click();

  // Outlasts the 4s poll, which clears the ordinary error line on every load.
  await expect(page.getByTestId("delete-error")).toHaveText(reason);
  await page.waitForTimeout(4500);
  await expect(page.getByTestId("delete-error")).toHaveText(reason);
  await expect(page).toHaveURL(new RegExp(`/chats/${id}$`));
  await expect(page.getByText("Please delete this test conversation.")).toBeVisible();
});
