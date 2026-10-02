/**
 * E2E for RF-2: post-go-live editing of the business identity.
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * The specs share one seeded tenant, so every edit is restored before the test
 * ends - the storefront spec pins the seeded hours and services text.
 */

import { expect, test, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;
const ORIGINAL_NAME = "Bytefix Repairs";
const ORIGINAL_HOURS = "Monday to Friday 9am to 6pm, Saturday 10am to 2pm";

/** Open a field row, replace its value, save, and wait for the sheet to close. */
async function saveField(page: Page, row: string, field: string, value: string) {
  await page.getByRole("button", { name: new RegExp(`^${row}\\b`) }).click();
  const input = page.getByTestId(`profile-${field}-input`);
  await expect(input).toBeVisible();
  await input.fill(value);
  await page.getByTestId(`profile-${field}-save`).click();
  await expect(input).toHaveCount(0);
}

/** Open Business contact, replace the value, save, and wait for the close. */
async function saveContact(page: Page, detail: string) {
  await page.getByRole("button", { name: /^Business contact\b/ }).click();
  const input = page.getByTestId("contact-detail-input");
  await expect(input).toBeVisible();
  await input.fill(detail);
  await page.getByTestId("contact-save").click();
  await expect(input).toHaveCount(0);
}

test.describe("RF-2 business details", () => {
  test("editing the name shows on the Business page and leaves the public address", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);

    await page.goto("/business/page");
    const addressBefore = await page.getByTestId("booking-link").textContent();
    expect(addressBefore).toContain("/bytefix");

    await page.goto("/business/details");
    await saveField(page, "Business name", "name", "Bytefix Renamed");
    await expect(page.getByRole("button", { name: /^Business name/ })).toContainText(
      "Bytefix Renamed",
    );

    await page.goto("/business/page");
    await expect(page.getByRole("heading", { level: 2 })).toContainText("Bytefix Renamed");
    // The public address is a separate, stable field: a rename never moves it.
    await expect(page.getByTestId("booking-link")).toHaveText(addressBefore!);

    await page.goto("/business/details");
    await saveField(page, "Business name", "name", ORIGINAL_NAME);
  });

  test("hours, description and contact appear on the Business page", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/details");

    await saveField(page, "Opening hours", "hours", "Mon to Fri 10am to 7pm");
    await saveField(page, "Description", "description", "A friendly repair shop.");
    await saveContact(page, "shop@bytefix.dev");

    await page.goto("/business/page");
    await expect(page.getByText(/Mon to Fri 10am to 7pm/)).toBeVisible();
    await expect(page.getByTestId("business-description")).toHaveText("A friendly repair shop.");
    await expect(page.getByTestId("business-contact")).toHaveText("shop@bytefix.dev");

    await page.goto("/business/details");
    await saveField(page, "Opening hours", "hours", ORIGINAL_HOURS);
    await saveField(page, "Description", "description", "");
    await saveContact(page, "");
  });

  test("the phone toggle swaps the contact field and Save stores the number", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/details");

    // Whatever the shared tenant currently holds, put it back at the end.
    await page.getByRole("button", { name: /^Business contact\b/ }).click();
    const original = await page.getByTestId("contact-detail-input").inputValue();
    await page.getByTestId("contact-cancel").click();

    await page.getByRole("button", { name: /^Business contact\b/ }).click();
    await page.getByTestId("contact-phone-toggle").click();
    const phone = page.getByTestId("contact-phone-input");
    await expect(phone).toBeVisible();
    await expect(page.getByTestId("contact-detail-input")).toHaveCount(0);
    await phone.fill("0412345678");

    // The toggle flips to "Email" and brings the text field back holding the
    // formatted number; Save is the only submit. Activated by keyboard: the
    // dev-only Next.js indicator sits over the sheet's bottom-left and would
    // swallow a pointer click on the narrower "Email" button.
    await page.getByTestId("contact-phone-toggle").press("Enter");
    await expect(page.getByTestId("contact-detail-input")).toHaveValue("+61 0412 345 678");
    await page.getByTestId("contact-save").click();

    await page.goto("/business/page");
    await expect(page.getByTestId("business-contact")).toHaveText("+61 0412 345 678");

    await page.goto("/business/details");
    await saveContact(page, original);
  });

  test("removing a service asks first and only edits the draft", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/details");

    const servicesRow = page.getByRole("button", { name: /^Services\b/ });
    await servicesRow.click();
    const sheet = page.getByRole("dialog", { name: "Edit services" });
    const removes = page.getByTestId("service-remove");
    const count = await removes.count();
    expect(count).toBeGreaterThan(1);

    // Cancel keeps the row.
    await removes.first().click();
    const confirm = page.getByRole("dialog", { name: "Remove this service?" });
    await expect(confirm).toBeVisible();
    await confirm.getByRole("button", { name: "Cancel" }).click();
    await expect(removes).toHaveCount(count);

    // Confirming drops it from the draft only.
    await removes.first().click();
    await page.getByTestId("confirm-accept").click();
    await expect(removes).toHaveCount(count - 1);

    // Closing without Save leaves the stored list untouched.
    await sheet.getByRole("button", { name: "Close" }).click();
    await servicesRow.click();
    await expect(page.getByTestId("service-remove")).toHaveCount(count);
    await sheet.getByRole("button", { name: "Close" }).click();
  });

  test("the existing services editor still saves", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/details");

    const row = page.getByRole("button", { name: /^Services\b/ });
    await row.click();
    // `exact` so the "Remove service 1" button's accessible name does not also
    // match the "Service 1" label.
    const first = page.getByLabel("Service 1", { exact: true });
    const original = await first.inputValue();
    await first.fill("RF-2 probe service");
    await page.getByTestId("services-save").click();
    await expect(page.getByRole("button", { name: /^Services\b/ })).toContainText(
      "RF-2 probe service",
    );

    await page.getByRole("button", { name: /^Services\b/ }).click();
    await page.getByLabel("Service 1", { exact: true }).fill(original);
    await page.getByTestId("services-save").click();
    await expect(page.getByRole("button", { name: /^Services\b/ })).toContainText(original);
  });
});
