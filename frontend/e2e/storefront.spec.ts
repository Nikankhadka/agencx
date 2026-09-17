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
  test("the owner and public page do not expose an About section", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");
    await expect(page.getByTestId("storefront-about")).toHaveCount(0);

    await page.goto("/bytefix");
    await expect(page.getByTestId("storefront-about")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Repairs", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Phones", exact: true })).toBeVisible();
  });

  test("a customer can open a conversation from the page", async ({ page }) => {
    await page.goto("/bytefix");

    // The page leads with who the business is, not with a chat box.
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Bytefix");

    await page.getByRole("button", { name: "Chat with Bytefix" }).click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    await expect(sheet).toContainText("Bytefix");
  });

  test("offers one customer-facing chat entry", async ({ page }) => {
    await page.goto("/bytefix");
    const chatEntries = page.getByRole("button", { name: "Chat with Bytefix" });
    await expect(chatEntries).toHaveCount(1);
    await expect(chatEntries).toHaveText("");
    await expect(page.getByRole("button", { name: "Ask a question" })).toHaveCount(0);
  });

  // D26: the stored tenant accent is accepted but no longer rendered. Both demo
  // tenants have one, so a re-injected override would show as a non-Rausch fill.
  test("the stored tenant accent does not recolor the chat entry", async ({ page }) => {
    for (const tenant of [
      { slug: "bytefix", name: "Bytefix Repairs" },
      { slug: "lumident", name: "Lumident Dental" },
    ]) {
      await page.goto(`/${tenant.slug}`);
      const cta = page.getByRole("button", { name: `Chat with ${tenant.name}` });
      await expect(cta).toBeVisible();
      const background = await cta.evaluate((el) => getComputedStyle(el).backgroundColor);
      expect(background).toBe("rgb(255, 56, 92)");
    }
  });

  /**
   * W-9 US-8: the assistant says what it is before anything else, and a tenant
   * that configured its own welcome is not greeted a second time. Both demo
   * tenants have a configured `config->customer.greeting` and both of those
   * greetings open with a hello, so this is the case that used to double up.
   * `lib/greeting.test.ts` covers the normalizer; this is the surface.
   */
  for (const tenant of [
    { slug: "bytefix", name: "Bytefix Repairs", adds: "I can quote a repair" },
    { slug: "lumident", name: "Lumident Dental", adds: "I can help you understand a treatment" },
  ]) {
    test(`${tenant.slug} opens with the identity line and greets once`, async ({ page }) => {
      await page.goto(`/${tenant.slug}`);
      await page.getByRole("button", { name: `Chat with ${tenant.name}` }).click();
      const sheet = page.getByRole("dialog", { name: `Chat with ${tenant.name}` });
      await expect(sheet).toBeVisible();

      const identity = `Hi, I'm ${tenant.name}'s assistant. How can I help today?`;
      await expect(sheet).toContainText(identity);

      // The identity line leads; the configured welcome is what follows it.
      const opening = await sheet.innerText();
      expect(opening.indexOf(identity)).toBeGreaterThanOrEqual(0);
      expect(opening.indexOf(tenant.adds)).toBeGreaterThan(opening.indexOf(identity));

      // And hello is said exactly once, by the identity line.
      expect(opening.match(/\b(hi|hello|hey)\b/gi) ?? []).toHaveLength(1);
    });
  }

  test("an unknown slug still gets the calm not-found page", async ({ page }) => {
    await page.goto("/no-such-business");
    // Asserted on what renders, not on the status: Next streams this page, so
    // `notFound()` after the first byte still returns 200 with the error shell
    // - the same trap the deploy smoke test documents (deploy.md, B-4).
    await expect(page.getByText("There's no business here.")).toBeVisible();
  });

  /**
   * M-7 US-1/US-4: bytefix is the no-photo base - 15 offerings, zero media.
   * The page leads with profile facts, rows reserve no media space, and the
   * seeded contact address never reaches the customer surface.
   */
  test("the no-photo base shows profile facts and no contact", async ({ page }) => {
    await page.goto("/bytefix");

    await expect(page.getByRole("heading", { level: 1 })).toContainText("Bytefix");
    await expect(page.getByText("phone repair shop")).toBeVisible();
    await expect(
      page.getByText(
        "Phone and laptop repairs, screen replacements, battery replacements, data recovery",
      ),
    ).toBeVisible();
    await expect(
      page.getByText("Monday to Friday 9am to 6pm, Saturday 10am to 2pm"),
    ).toBeVisible();
    await expect(page.getByText("owner@bytefix.dev")).toHaveCount(0);
    // The veil band stands in the cover's place, and no image is reserved.
    await expect(page.getByTestId("hero-veil")).toBeVisible();
    await expect(page.locator("main img")).toHaveCount(0);
  });

  test("the hero monogram overlaps the veil band", async ({ page }) => {
    await page.goto("/bytefix");

    // v4 fallback B: the mark sits on the band, not below it. A block-level
    // wrapper carries the -mt-12; an inline one silently fails to shift.
    const band = await page.getByTestId("hero-veil").boundingBox();
    const mark = await page.getByTestId("hero-mark").boundingBox();
    expect(band).not.toBeNull();
    expect(mark).not.toBeNull();
    expect(band!.y + band!.height - mark!.y).toBeGreaterThan(20);
  });

  test("rows carry no reserved media space", async ({ page }) => {
    await page.goto("/bytefix");

    // The old composition held every row at min-h-36 (144px) for media that
    // was never coming. A text-only row is only as tall as its text.
    const row = page.getByRole("button", { name: /iPhone 11 \(Refurbished, 64GB\)/ });
    await expect(row).toBeVisible();
    const box = await row.boundingBox();
    expect(box, "text-only row must not reserve thumbnail space").not.toBeNull();
    expect(box!.height).toBeLessThan(144);
  });

  test("the desktop category nav follows the menu", async ({ page }) => {
    await page.goto("/bytefix");

    const repairs = page.locator("aside").getByRole("link", { name: "Repairs" });
    await repairs.click();
    await expect(repairs).toHaveAttribute("aria-current", "true");
  });

  test("the header identity returns to the top", async ({ page }) => {
    await page.goto("/bytefix");

    await page.locator("aside").getByRole("link", { name: "Repairs" }).click();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);

    await page.getByRole("button", { name: "Back to top" }).click();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  });
});
