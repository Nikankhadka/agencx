/**
 * E2E for RF-16: explicit issue resolution in the conversation workspace.
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * An open issue is resolved from the thread - its own confirmation, an
 * owner-only `thr-pill` stamp, and an optional customer-facing message.
 * Replying and handing back stay separate and never resolve. After resolving,
 * the issue leaves Needs you, the stamp survives a refresh, and the customer
 * transcript shows the message but never the stamp.
 *
 * Deliberately model-free: the conversation and its open escalation are created
 * through the live deterministic `POST /api/chat/handoff` endpoint, so an open
 * issue exists without a model deciding to escalate. Resolution is available
 * from Handling, before any takeover.
 */

import { expect, test, type APIRequestContext } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SLUG = "bytefix";

/**
 * Create a customer conversation with an open escalation, no model involved:
 * the handoff endpoint writes the same escalation row the assistant's tool
 * would and streams the conversation id, exactly as a customer's "ask for a
 * person" would.
 */
async function openHandoffConversation(request: APIRequestContext): Promise<string> {
  const opened = await request.post(`${API_URL}/api/chat/handoff`, {
    data: { slug: SLUG },
  });
  expect(opened.ok()).toBeTruthy();
  const conversationId = /"conversation_id": ?"([0-9a-f-]{36})"/.exec(await opened.text())?.[1];
  expect(conversationId).toBeTruthy();
  return conversationId!;
}

const RESOLUTION_STAMP = "You resolved this issue";

test("the owner resolves an open issue from the thread", async ({ page, request }) => {
  const conversationId = await openHandoffConversation(request);
  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  await page.goto(`/chats/${conversationId}`);

  // RF-15: at desktop the queue list sits beside the thread, and its preview
  // can repeat a message or a stamp. Scope transcript assertions to the thread
  // pane so they cannot match both.
  const thread = page.getByTestId("chats-thread-pane");

  // Resolution is available from Handling, before any takeover.
  await expect(page.getByTestId("thread-status")).toHaveText("Handling");
  await expect(thread.getByTestId("resolve-issue")).toBeVisible();

  await thread.getByTestId("resolve-issue").click();
  const message = "All sorted - a team member will call you shortly.";
  await thread.getByTestId("resolve-message").fill(message);
  await thread.getByTestId("resolve-submit").click();
  // Explicit confirmation is the whole point: resolution is its own action.
  await page.getByTestId("confirm-accept").click();

  // The owner-only stamp and the optional customer message both land.
  await expect(thread.getByText(RESOLUTION_STAMP)).toBeVisible();
  await expect(thread.getByText(message)).toBeVisible();

  // Both survive a refresh, and the issue left Needs you - the control is gone.
  await page.reload();
  await expect(thread.getByText(RESOLUTION_STAMP)).toBeVisible();
  await expect(thread.getByText(message)).toBeVisible();
  await expect(thread.getByTestId("resolve-issue")).toHaveCount(0);

  // The customer sees the message and never the owner-only stamp.
  const transcript = await request.get(
    `${API_URL}/api/chat/${conversationId}/messages?slug=${SLUG}`
  );
  const messages = (await transcript.json()) as { role: string; content: string }[];
  expect(messages.some((m) => m.role === "human_agent" && m.content === message)).toBeTruthy();
  expect(messages.some((m) => m.content === RESOLUTION_STAMP)).toBeFalsy();
});

test("replying and handing back never resolve the issue", async ({ page, request }) => {
  const conversationId = await openHandoffConversation(request);
  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  await page.goto(`/chats/${conversationId}`);

  const thread = page.getByTestId("chats-thread-pane");
  await expect(thread.getByTestId("resolve-issue")).toBeVisible();

  // Take over and reply - the assistant stays quiet, but the issue does not
  // close just because a human spoke.
  await page.getByTestId("take-over").click();
  await expect(page.getByTestId("thread-status")).toHaveText("You're replying");

  const reply = "Hi, it's Sam from ByteFix - happy to help.";
  await thread.getByRole("textbox").fill(reply);
  await page.keyboard.press("Enter");
  await expect(thread.getByText(reply)).toBeVisible();

  // Hand back - the assistant resumes, and the issue is still open.
  await page.getByTestId("hand-back").click();
  await page.getByTestId("confirm-accept").click();
  await expect(page.getByTestId("thread-status")).toHaveText("Handling");

  await expect(thread.getByTestId("resolve-issue")).toBeVisible();
  await expect(thread.getByText(RESOLUTION_STAMP)).toHaveCount(0);

  // F8 hygiene: this test opened an escalation in the shared serial demo world.
  // Resolve it through the UI, which both proves resolution works after a
  // handback and leaves no escalated row behind for later tests. No message.
  await thread.getByTestId("resolve-issue").click();
  await thread.getByTestId("resolve-submit").click();
  await page.getByTestId("confirm-accept").click();
  await expect(thread.getByTestId("resolve-issue")).toHaveCount(0);
});
