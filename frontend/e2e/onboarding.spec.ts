import { expect, test } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

/**
 * Regression for the 401 "missing bearer token" on the onboarding chat's
 * first message (T-042 / onboarding stream): the stream POST must carry the
 * Supabase session token, and a reply must stream in as SSE.
 */
test("onboarding first message streams a reply", async ({ page }) => {
  await loginAsTenantAdmin(page, DEMO_USERS[0]);

  await expect(page.getByRole("heading", { name: "Onboarding" })).toBeVisible();

  const assistantBubbles = page.locator("div.bg-surface");
  const prompt = await assistantBubbles.first().textContent();
  expect(prompt?.trim().length).toBeGreaterThan(0);

  await page.getByLabel("Your reply").fill("I run a phone repair shop.");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(
    page.getByText("I run a phone repair shop.", { exact: true })
  ).toBeVisible();

  // The fresh assistant bubble streams in a non-empty reply; a 401 would
  // surface as an error line instead and this never resolves.
  await expect(assistantBubbles.last()).not.toHaveText("", { timeout: 60_000 });
  await expect(page.getByText("onboarding request failed")).toHaveCount(0);
});
