/**
 * E2E for the public storefront (M-4).
 *
 * Surface: customer (http://localhost:3000/{slug}), written by the owner from
 * the console.
 *
 * The round trip is the point: what the owner types in Business is what a
 * customer reads at `/{slug}`, with nothing in between rewriting it. The
 * offerings-and-price half of that trip lives in business-hub.spec.ts, where
 * the editor is; this file covers the sections the storefront adds and the
 * way a customer gets from the page into a conversation.
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

test.describe("the public storefront", () => {
  test("the owner's About reaches the page a customer reads", async ({
    page,
    request,
  }) => {
    const about = "We fix phones on Smith Street, most repairs same day.";

    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");

    // No settle-loop needed: the editor's fields are disabled until it has
    // loaded the current sections, and `fill` waits for enabled - which is
    // also what stops an owner's first sentence being eaten by that response.
    await page.getByTestId("storefront-about").fill(about);
    await page.getByTestId("storefront-save").click();
    await expect(page.getByTestId("storefront-save")).toContainText("Saved");

    await page.goto("/bytefix");
    await expect(page.getByRole("main").last()).toContainText(about);

    // Put the shared seeded tenant back as it was found.
    await page.goto("/business/page");
    await page.getByTestId("storefront-about").fill("");
    await page.getByTestId("storefront-save").click();
    await expect(page.getByTestId("storefront-save")).toContainText("Saved");
  });

  test("a customer can open a conversation from the page", async ({ page }) => {
    await page.goto("/bytefix");

    // The page leads with who the business is, not with a chat box.
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Bytefix");

    await page.getByRole("button", { name: "Ask a question" }).click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    await expect(sheet).toContainText("Bytefix");
  });

  test("an unknown slug still gets the calm not-found page", async ({ page }) => {
    await page.goto("/no-such-business");
    // Asserted on what renders, not on the status: Next streams this page, so
    // `notFound()` after the first byte still returns 200 with the error shell
    // - the same trap the deploy smoke test documents (deploy.md, B-4).
    await expect(page.getByText("There's no business here.")).toBeVisible();
  });
});
