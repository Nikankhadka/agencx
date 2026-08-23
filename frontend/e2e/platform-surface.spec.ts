/**
 * E2E for the platform-owner surface (E-3).
 *
 * Surface: platform (http://admin.localhost:3000)
 *
 * E-3 is a verification ticket - no new platform features land in Stage 1 -
 * so this spec exists to hold the surface to its job: list tenants with the
 * numbers to watch, provision one, and suspend or reactivate with the
 * consequence that reaches the customer.
 *
 * The suspension test is the one worth having, and the one that needs care:
 * it is the only control here whose effect lands on a different surface
 * entirely, and the only test in the suite that mutates a tenant other tests
 * read. It therefore heals its own starting state and restores it afterwards -
 * a first run that failed halfway once left `lumident` suspended, and every
 * later run then failed looking for a Suspend button that had become
 * Reactivate.
 */

import { test, expect, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsPlatformAdmin, platformHost } from "./auth-helpers";

const FOUNDER = DEMO_USERS.find((u) => u.surface === "platform")!;
const TENANT = "lumident";

/** The row's action button is the tenant's status, in the only place it acts. */
function actionFor(page: Page, label: "Suspend" | "Reactivate") {
  return page.getByRole("row").filter({ hasText: TENANT }).getByRole("button", { name: label });
}

/** Put the tenant back to active, whatever state a previous step left it in. */
async function ensureActive(page: Page) {
  await page.goto(`http://${platformHost()}`);
  // Wait for the row before asking which button it carries. `count()` does not
  // retry, so checking it against a table that has not fetched yet reads zero
  // and quietly decides there is nothing to restore - which is how the tenant
  // stayed suspended between runs.
  await expect(page.getByRole("row").filter({ hasText: TENANT })).toBeVisible();
  if ((await actionFor(page, "Reactivate").count()) > 0) {
    await actionFor(page, "Reactivate").click();
    await page.getByRole("dialog", { name: "Reactivate tenant" }).getByRole("button", { name: "Reactivate" }).click();
    await expect(actionFor(page, "Suspend")).toBeVisible();
  }
}

test.describe("the platform owner's one page", () => {
  test.use({ baseURL: `http://${platformHost()}` });

  test("lists every tenant with the numbers worth watching", async ({ page }) => {
    await loginAsPlatformAdmin(page, FOUNDER);

    for (const header of ["Name", "Slug", "Status", "Created", "Conversations", "Cost"]) {
      await expect(page.getByRole("columnheader", { name: header })).toBeVisible();
    }
    // The aggregate a founder checks first.
    await expect(page.getByText("Total cost")).toBeVisible();
  });

  test("provisioning refuses a slug already in use, before submitting", async ({ page }) => {
    await loginAsPlatformAdmin(page, FOUNDER);
    await page.getByRole("button", { name: "Provision tenant" }).click();

    // Named, because every Modal on this page is in the DOM at once and only
    // its title tells them apart.
    const dialog = page.getByRole("dialog", { name: "Provision tenant" });
    await expect(dialog).toBeVisible();

    // A collision found server-side is a worse experience and a worse row.
    await dialog.getByLabel(/slug/i).fill(TENANT);
    await expect(dialog.getByText("Already taken")).toBeVisible();
  });
});

test.describe("suspension reaches the customer", () => {
  test.use({ baseURL: `http://${platformHost()}` });

  test.afterEach(async ({ page }) => {
    await ensureActive(page);
  });

  test("a suspended tenant's page goes quiet, and reactivating brings it back", async ({
    page,
  }) => {
    await loginAsPlatformAdmin(page, FOUNDER);
    await ensureActive(page);

    await actionFor(page, "Suspend").click();
    await page
      .getByRole("dialog", { name: "Suspend tenant" })
      .getByRole("button", { name: "Suspend" })
      .click();
    await expect(actionFor(page, "Reactivate")).toBeVisible();

    // The consequence, on the surface the customer actually visits.
    await page.goto(`http://${TENANT}.localhost:3000`);
    // Scoped to main: Next's dev-mode RSC payload carries the same sentence in
    // a script tag, and an unscoped getByText matches both.
    const quiet = page.locator("main");
    // And settled first: `next dev` streams the server tree and the client
    // tree into the DOM together for a beat after load, so there are two of
    // everything - including this main - until it resolves (the same artifact
    // typing-indicator.spec.ts waits out).
    await expect(quiet).toHaveCount(1);
    await expect(quiet.getByText("currently unavailable")).toBeVisible();

    // B-1's copy rules apply to states copy-rules.spec.ts cannot reach without
    // mutating a tenant. This one is already suspended, so it is checked here.
    // It read "This assistant is currently unavailable" until E-3 found it.
    const said = await quiet.innerText();
    expect(said).not.toMatch(/\bassistants?\b/i);
    // And it says nothing about why: a customer is not owed a billing state.
    expect(said).not.toMatch(/\bsuspend|\bbilling|\bpayment/i);

    // And back.
    await ensureActive(page);
    await page.goto(`http://${TENANT}.localhost:3000`);
    await expect(page.locator("main").getByText("currently unavailable")).toHaveCount(0);
  });
});
