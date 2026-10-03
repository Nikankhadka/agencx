/**
 * E2E for RF-7: contextual owner edit shortcuts on the public storefront.
 *
 * Surface: customer (http://localhost:3000/{slug}), reached by the signed-in
 * owner. The shortcuts reuse the RF-2 editors, so every edit is restored
 * before the test ends (the storefront and RF-2 specs pin the seeded values).
 *
 * Owner detection is server-side: the matching tenant owner sees the controls,
 * everyone else (a customer or another tenant) gets the unchanged customer DOM.
 */

import { expect, test, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;
const ORIGINAL_NAME = "Bytefix Repairs";
const ORIGINAL_HOURS = "Monday to Friday 9am to 6pm, Saturday 10am to 2pm";
const ORIGINAL_CONTACT = "owner@bytefix.dev";
const PRICED_OFFERING = "iPhone 11 (Refurbished, 64GB)";

/** next dev streams the page, briefly rendering two trees; retry until the
 *  shortcut's click lands on the live tree and its editor opens. */
async function openEditor(page: Page, shortcut: string, input: string) {
  await expect(async () => {
    await page.getByTestId(shortcut).click();
    await expect(page.getByTestId(input)).toBeVisible();
  }).toPass({ timeout: 15_000 });
}

test.describe("RF-7 storefront owner shortcuts", () => {
  test("the owner sees and can open every shortcut", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/bytefix");

    await expect(async () => {
      await expect(page.getByTestId("owner-edit-name")).toBeVisible();
      await expect(page.getByTestId("owner-edit-hours")).toBeVisible();
      await expect(page.getByTestId("owner-edit-description")).toBeVisible();
      await expect(page.getByTestId("owner-edit-contact")).toBeVisible();
    }).toPass({ timeout: 15_000 });

    // Description opens the shared multiline editor; Cancel closes it.
    await openEditor(page, "owner-edit-description", "profile-description-input");
    await page.getByTestId("profile-description-cancel").click();
    await expect(page.getByTestId("profile-description-input")).toHaveCount(0);

    // Contact opens the one contact editor and Save stores the current value.
    // The shared tenant's contact is mutated by other specs, so this captures
    // whatever is current, proves the round trip, then restores it.
    await openEditor(page, "owner-edit-contact", "contact-detail-input");
    const originalContact = await page.getByTestId("contact-detail-input").inputValue();
    await page.getByTestId("contact-detail-input").fill("rf7-contact@example.com");
    await page.getByTestId("contact-save").click();
    await expect(page.getByTestId("contact-detail-input")).toHaveCount(0);

    await openEditor(page, "owner-edit-contact", "contact-detail-input");
    await expect(page.getByTestId("contact-detail-input")).toHaveValue(
      "rf7-contact@example.com",
    );
    await page.getByTestId("contact-detail-input").fill(originalContact);
    await page.getByTestId("contact-save").click();
    await expect(page.getByTestId("contact-detail-input")).toHaveCount(0);
  });

  test("editing the name from the storefront updates the page after Save", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/bytefix");

    await openEditor(page, "owner-edit-name", "profile-name-input");
    await expect(page.getByTestId("profile-name-input")).toHaveValue(ORIGINAL_NAME);
    await page.getByTestId("profile-name-input").fill("Bytefix RF7");
    await page.getByTestId("profile-name-save").click();
    await expect(page.getByTestId("profile-name-input")).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Bytefix RF7");

    // Restore the shared seeded tenant.
    await openEditor(page, "owner-edit-name", "profile-name-input");
    await page.getByTestId("profile-name-input").fill(ORIGINAL_NAME);
    await page.getByTestId("profile-name-save").click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(ORIGINAL_NAME);
  });

  test("editing the hours from the storefront updates the chip after Save", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/bytefix");

    await openEditor(page, "owner-edit-hours", "profile-hours-input");
    await expect(page.getByTestId("profile-hours-input")).toHaveValue(ORIGINAL_HOURS);
    await page.getByTestId("profile-hours-input").fill("Mon to Fri 10am to 7pm");
    await page.getByTestId("profile-hours-save").click();
    await expect(page.getByTestId("profile-hours-input")).toHaveCount(0);
    await expect(page.getByText("Mon to Fri 10am to 7pm")).toBeVisible();

    // Restore.
    await openEditor(page, "owner-edit-hours", "profile-hours-input");
    await page.getByTestId("profile-hours-input").fill(ORIGINAL_HOURS);
    await page.getByTestId("profile-hours-save").click();
    await expect(page.getByText(ORIGINAL_HOURS)).toBeVisible();
  });

  test("Cancel changes nothing", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/bytefix");

    await openEditor(page, "owner-edit-name", "profile-name-input");
    await page.getByTestId("profile-name-input").fill("Should not stick");
    await page.getByTestId("profile-name-cancel").click();
    await expect(page.getByTestId("profile-name-input")).toHaveCount(0);

    await page.reload();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(ORIGINAL_NAME);
    await expect(page.getByRole("heading", { level: 1 })).not.toContainText("Should not stick");
  });

  test("an anonymous visitor's page has no owner controls and no contact value", async ({
    browser,
  }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    try {
      await page.goto("/bytefix");
      await expect(async () => {
        await expect(page.getByRole("heading", { level: 1 })).toContainText("Bytefix");
        await expect(page.getByTestId("owner-edit-name")).toHaveCount(0);
        await expect(page.getByTestId("owner-edit-hours")).toHaveCount(0);
        await expect(page.getByTestId("owner-edit-fields")).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Edit business name" })).toHaveCount(0);
      }).toPass({ timeout: 15_000 });

      const body = await page.locator("body").innerText();
      expect(body).not.toContain(ORIGINAL_CONTACT);
      expect(body).not.toContain("Add how customers reach you");
    } finally {
      await context.close();
    }
  });

  test("the storefront shows the same price as the owner editor at 360 and 1024", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    const namePattern = new RegExp(PRICED_OFFERING.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));

    for (const width of [360, 1024]) {
      await page.setViewportSize({ width, height: 900 });

      await page.goto("/bytefix");
      const row = page.getByRole("button", { name: namePattern }).first();
      await expect(row).toBeVisible();
      const price = await row.getByTestId("offering-price").textContent();
      expect(price, `storefront price at ${width}px`).toBe("$249.00");

      await page.goto("/business/offerings");
      const list = page.getByTestId("offerings-list");
      await expect(list).toBeVisible();
      const item = list
        .getByText(PRICED_OFFERING, { exact: true })
        .first()
        .locator("xpath=ancestor::li[1]");
      await expect(item).toContainText(price!);
    }
  });
});
