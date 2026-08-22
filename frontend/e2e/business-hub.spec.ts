/**
 * E2E for the Business hub and its Booking page (E-5 / D21).
 *
 * Surface: tenant-admin (http://app.localhost:3000)
 *
 * The hub's shape is the thing under test as much as its contents: Stage 2
 * grows it by adding rows, so "exactly the rows that open onto something" is
 * the invariant worth pinning (PRD, "never build dead surfaces").
 */

import { test, expect } from "@playwright/test";
import {
  DEMO_USERS,
  loginAsTenantAdmin,
  tenantAdminHost,
} from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;
const STAGE_2_ROWS = ["Schedule", "Money", "Plan"];

test.describe("Business hub", () => {
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  test("holds only rows that open onto something", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");

    const rows = page.getByRole("main").getByRole("link");
    await expect(rows).toHaveText([
      "Booking pageWhat customers see, and the link to it",
      "SettingsWhat your customers are told",
    ]);

    // Absent, not disabled - the prototype carries them, Stage 1 does not.
    for (const label of STAGE_2_ROWS) {
      await expect(page.getByText(label, { exact: true })).toHaveCount(0);
    }
  });

  test("the booking page shows the business and its public link", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");
    await page.getByRole("link", { name: /Booking page/ }).click();
    await page.waitForURL("**/business/booking");

    await expect(page.getByRole("heading", { level: 2 })).toContainText(
      "Bytefix",
    );

    // Derived from the current host, so it is the address that actually works
    // from this browser - never a hardcoded domain.
    const link = page.getByTestId("booking-link");
    await expect(link).toContainText("bytefix.");
    await expect(link).not.toContainText("http");
    await expect(link).not.toContainText(/\/$/);
  });

  test("copying puts the full URL, scheme and all, on the clipboard", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/booking");

    await page.getByTestId("booking-copy").click();
    await expect(page.getByTestId("booking-copy")).toContainText("Copied");

    const copied = await page.evaluate(() => navigator.clipboard.readText());
    // The pill hides the scheme; what a customer needs is the whole thing.
    expect(copied).toMatch(/^https?:\/\/bytefix\./);
    expect(copied.endsWith("/")).toBe(false);
  });

  test("the cover photo, the services list and the link slots", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/booking");

    // E-6: the QR went. It was never in the prototype's owner screen, and the
    // founder does not use it. Pinned so it does not drift back in.
    await expect(page.getByTestId("booking-qr")).toHaveCount(0);
    // Nor is there a "Get a quote" CTA: quoting is a Stage 2 opt-in.
    await expect(page.getByRole("button", { name: "Get a quote" })).toHaveCount(
      0,
    );

    // The cover well invites a photo before there is one.
    await expect(page.getByTestId("booking-cover")).toBeVisible();
    await expect(page.getByTestId("booking-cover")).toContainText(
      "cover photo",
    );

    // Four slots, each either offering to take a link or offering to open one.
    // Not asserted as "all empty": these specs share one seeded tenant, so a
    // slot's contents are another test's business, not this one's.
    for (const key of ["website", "google", "facebook", "instagram"]) {
      await expect(page.getByTestId(`booking-platform-${key}`)).toContainText(
        /Add|Open/,
      );
    }
  });

  test("a link slot takes an address, keeps it, and then opens it", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/booking");

    const tile = page.getByTestId("booking-platform-instagram");

    // These specs share one seeded tenant, so start from a known slot rather
    // than from whatever a previous run left behind.
    await tile.click();
    if (await page.getByTestId("booking-link-remove").isVisible()) {
      await page.getByTestId("booking-link-remove").click();
      await expect(tile).toContainText("Add");
      await tile.click();
    }

    // Pasted without a scheme, the way an address bar shows it.
    await page.getByTestId("booking-link-input").fill("instagram.com/bytefix");
    await page.getByTestId("booking-link-save").click();
    await expect(tile).toContainText("Open");

    // It survives a reload - this is the assertion that catches a save that
    // only ever updated local state.
    await page.reload();
    await expect(tile).toContainText("Open");

    // And it is a way out to that page, with the scheme filled in. Asserted on
    // the href rather than by following it: a real popup would assert on
    // whatever instagram.com redirects to that day, which is a test of their
    // infrastructure, not ours.
    await tile.click();
    await expect(page.getByTestId("booking-link-open")).toHaveAttribute(
      "href",
      "https://instagram.com/bytefix",
    );

    // Put the slot back, so this spec leaves the shared tenant as it found it.
    await page.getByTestId("booking-link-remove").click();
    await expect(tile).toContainText("Add");
  });

  test("back from the booking page returns to the hub", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/booking");
    await page.getByRole("button", { name: "Back" }).click();
    await page.waitForURL("**/business");
  });
});
