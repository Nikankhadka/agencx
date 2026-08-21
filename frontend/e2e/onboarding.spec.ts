import { expect, test } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

/**
 * Regression for the 401 "missing bearer token" on the onboarding chat's
 * first message (T-042 / onboarding stream): the stream POST must carry the
 * Supabase session token, and a reply must stream in as SSE.
 */
test("onboarding first message streams a reply", async ({ page, request }) => {
  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  // The onboarding thread IS the screen: no heading, and no console chrome
  // (agencx-prototype-v6.html shows no navigation until the business is live).
  await expect(page.getByRole("log", { name: "Onboarding conversation" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Console" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Onboarding" })).toHaveCount(0);

  const thread = page.getByTestId("onboarding-thread");
  const prompt = await thread.textContent();
  expect(prompt?.trim().length).toBeGreaterThan(0);

  const composer = page.getByTestId("onboarding-composer");
  await composer.getByRole("textbox").fill("I run a phone repair shop.");
  await composer.getByRole("button", { name: "Send" }).click();

  // The customer message echoes into the thread...
  await expect(thread.getByText("I run a phone repair shop.", { exact: true })).toBeVisible();

  // ...and the stream resolves without an error line (a 401 surfaces there).
  await expect(page.getByTestId("onboarding-error")).toHaveCount(0);
});
