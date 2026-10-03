/**
 * E2E for RF-8: the desktop customer-chat panel and the mobile full-height
 * sheet.
 *
 * Surface: customer (http://localhost:3000/{slug}), seeded by
 * seed_tenant1_phoneshop (bytefix). The one chat host switches presentation
 * at `lg` (1024px): a docked, non-modal right panel above it, the modal
 * bottom sheet below.
 */

import { expect, test } from "@playwright/test";

const SLUG = "bytefix";
const CHAT_BUTTON = "Chat with Bytefix Repairs";
const OFFERING = /iPhone 11 \(Refurbished, 64GB\)/;

/** next dev streams the page; retry the open until the panel is live. */
async function openChat(page: import("@playwright/test").Page) {
  // The docked panel is named; the storefront's browse sidebar is another
  // `complementary` landmark, so the chat panel is always addressed by name.
  const panel = page.getByRole("complementary", { name: CHAT_BUTTON });
  const sheet = page.getByRole("dialog", { name: CHAT_BUTTON });
  await expect(async () => {
    await page.getByRole("button", { name: CHAT_BUTTON }).click();
    await expect(panel.or(sheet)).toBeVisible();
  }).toPass({ timeout: 15_000 });
}

test.describe("RF-8 desktop chat panel (1024px)", () => {
  test.use({ viewport: { width: 1024, height: 900 } });

  test("opens as a docked complementary panel beside the page", async ({ page }) => {
    await page.goto(`/${SLUG}`);
    await openChat(page);

    const panel = page.getByRole("complementary", { name: CHAT_BUTTON });
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("aria-label", CHAT_BUTTON);
    // Non-modal: no dialog role and no aria-modal at desktop.
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(panel).not.toHaveAttribute("aria-modal", "true");

    // It is docked right, not a full-width overlay.
    const box = await panel.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeLessThan(500);
    expect(box!.x + box!.width).toBeGreaterThan(1000);

    // It carries a close control.
    await expect(page.getByRole("button", { name: "Close chat" })).toBeVisible();
  });

  test("leaves the page visible, scrollable, and clickable", async ({ page }) => {
    await page.goto(`/${SLUG}`);
    await openChat(page);

    // The page is not hidden behind a scrim: the page content is still there.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    // The page scrolls while the panel is open.
    await page.evaluate(() => window.scrollTo(0, 400));
    const scrolled = await page.evaluate(() => window.scrollY);
    expect(scrolled).toBeGreaterThan(0);

    // A page control is still clickable: the offering row opens its sheet.
    await page.getByRole("button", { name: OFFERING }).first().click();
    const detail = page.getByRole("dialog", { name: OFFERING });
    await expect(detail).toBeVisible();
  });

  test("closing returns to the page and keeps the scroll position", async ({ page }) => {
    await page.goto(`/${SLUG}`);
    await openChat(page);

    await page.evaluate(() => window.scrollTo(0, 300));
    await page.getByRole("button", { name: "Close chat" }).click();

    // Closed means the single host is inert (it stays mounted and translated
    // off-screen for the animation, so `toBeHidden` is not the signal).
    await expect(page.locator("[data-chat-host]")).toHaveAttribute("inert", "");
    await expect(page.getByRole("complementary", { name: CHAT_BUTTON })).toHaveCount(0);
    // The page scroll is not reset by closing.
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  });

  test("Escape closes the panel", async ({ page }) => {
    await page.goto(`/${SLUG}`);
    await openChat(page);

    await page.keyboard.press("Escape");
    await expect(page.locator("[data-chat-host]")).toHaveAttribute("inert", "");
    // The chat instance is never orphaned or duplicated: exactly one thread host.
    await expect(page.locator("[data-chat-host]")).toHaveCount(1);
  });

  test("moves focus into the panel on open and back to the opener on close", async ({
    page,
  }) => {
    await page.goto(`/${SLUG}`);
    const opener = page.getByRole("button", { name: CHAT_BUTTON });
    await opener.click();

    const panel = page.getByRole("complementary", { name: CHAT_BUTTON });
    await expect(panel).toBeVisible();
    // Focus moved into the panel.
    expect(await panel.evaluate((el) => el.contains(document.activeElement))).toBe(true);

    await page.keyboard.press("Escape");
    await expect(page.locator("[data-chat-host]")).toHaveAttribute("inert", "");
    // Focus returned to the control that opened the chat.
    expect(await opener.evaluate((el) => el === document.activeElement)).toBe(true);
  });
});

test.describe("RF-8 mobile chat sheet (360px)", () => {
  test.use({ viewport: { width: 360, height: 780 } });

  test("is a full-height modal sheet with the composer reachable", async ({ page }) => {
    await page.goto(`/${SLUG}`);
    await openChat(page);

    const sheet = page.getByRole("dialog", { name: CHAT_BUTTON });
    await expect(sheet).toBeVisible();

    // Full viewport height minus safe areas, not the old 85% cap.
    const box = await sheet.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(760);

    // The composer is reachable and inside the viewport.
    const input = sheet.getByLabel("Message");
    await expect(input).toBeVisible();
    const inputBox = await input.boundingBox();
    expect(inputBox).not.toBeNull();
    expect(inputBox!.y + inputBox!.height).toBeLessThanOrEqual(781);
  });

  test("keeps role=dialog, aria-modal, focus trap, and Escape close", async ({ page }) => {
    await page.goto(`/${SLUG}`);
    const opener = page.getByRole("button", { name: CHAT_BUTTON });
    await openChat(page);

    const sheet = page.getByRole("dialog", { name: CHAT_BUTTON });
    await expect(sheet).toHaveAttribute("aria-modal", "true");

    // Focus moved into the sheet.
    expect(await sheet.evaluate((el) => el.contains(document.activeElement))).toBe(true);

    // Tab wraps inside the sheet: tabbing never lands outside it.
    for (let i = 0; i < 12; i += 1) {
      await page.keyboard.press("Tab");
      expect(
        await sheet.evaluate((el) => el.contains(document.activeElement)),
        `focus escaped the sheet after ${i + 1} tabs`,
      ).toBe(true);
    }

    await page.keyboard.press("Escape");
    await expect(page.locator("[data-chat-host]")).toHaveAttribute("inert", "");
    // Focus returned to the opener.
    expect(await opener.evaluate((el) => el === document.activeElement)).toBe(true);
  });
});
