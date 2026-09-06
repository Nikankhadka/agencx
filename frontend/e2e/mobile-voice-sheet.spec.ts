/**
 * W-9 US-7 on a phone. Runs under the mobile-chrome project (matched by the
 * `mobile` in the filename), which is an iPhone 13 with a real touchscreen.
 *
 * This is the mobile half of what closes W-8's last open Definition-of-done
 * box: a bottom sheet is the one component that can look fine on a desktop and
 * still be unusable in a hand, so it is checked where it actually lives.
 */

import { expect, test, type Locator } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";
import { expectNoHorizontalOverflow } from "./mobile-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

/**
 * `expectTapTargets` from mobile-helpers scans the whole page, and this screen
 * has a control that fails it: `ScreenTopbar`'s Back button renders at the
 * prototype's 36px `--size-icon-btn`, under the 44px floor
 * design/frontend.md:633 sets, on all seven console screens that carry a
 * topbar. That is a real defect and it is reported as one - it is not the
 * voice sheet's, and fixing it moves a shared component's alignment on seven
 * screens, so it is not silently patched here either. This scans the sheet,
 * which is what this spec is actually about.
 */
async function expectSheetTapTargets(sheet: Locator, minPx = 44): Promise<void> {
  const undersized = await sheet.evaluate((panel: HTMLElement, min: number) => {
    const controls = panel.querySelectorAll<HTMLElement>(
      "button, [role='button'], input, select, textarea",
    );
    return Array.from(controls)
      .filter((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;
        return rect.height < min;
      })
      .map((el) => ({
        label: el.getAttribute("aria-label") ?? el.textContent?.trim().slice(0, 40) ?? "",
        height: Math.round(el.getBoundingClientRect().height),
      }));
  }, minPx);
  expect(undersized, "every control in the sheet must be >= 44px tall").toEqual([]);
}

test("the voice sheet is usable at phone width, by touch", async ({ page, request }) => {
  await loginAsTenantAdmin(page, request, BYTEFIX);
  await page.goto("/business/details");

  const row = page.getByRole("button", { name: /Assistant voice/ });
  await expect(row).toBeVisible();
  await expectNoHorizontalOverflow(page);

  // Tapped, not clicked - the row has to answer a finger.
  await row.tap();
  const sheet = page.getByRole("dialog", { name: "Edit assistant voice" });
  await expect(sheet).toBeVisible();

  // The sheet sits inside the viewport: it neither pushes the page sideways
  // nor runs off the bottom edge where its Save button cannot be reached.
  // Polled, because the panel slides up - measured on the first frame it is
  // still a screen's height below where it ends up.
  await expectNoHorizontalOverflow(page);
  const viewport = page.viewportSize()!;
  await expect
    .poll(async () => {
      const box = (await sheet.boundingBox())!;
      return Math.round(box.y + box.height);
    }, { message: "the sheet must come to rest inside the viewport" })
    .toBeLessThanOrEqual(viewport.height);
  const panel = (await sheet.boundingBox())!;
  expect(Math.round(panel.x)).toBeGreaterThanOrEqual(0);
  expect(Math.round(panel.x + panel.width)).toBeLessThanOrEqual(viewport.width);

  // Every control in the sheet, the four voice chips included, is tappable.
  await expectSheetTapTargets(sheet);
  for (const preset of ["warm_casual", "clear_professional", "direct_concise", "custom"]) {
    const chip = page.getByTestId(`voice-${preset}`);
    const box = (await chip.boundingBox())!;
    expect(box.height, `the ${preset} chip must be a tap target`).toBeGreaterThanOrEqual(44);
    expect(Math.round(box.x + box.width)).toBeLessThanOrEqual(viewport.width);
  }

  // The fourth chip's description field is reachable and typable on a phone,
  // and revealing it does not push the layout sideways.
  await page.getByTestId("voice-custom").tap();
  const style = page.getByTestId("voice-style");
  await expect(style).toBeVisible();
  await style.fill("Calm and reassuring, never pushy.");
  await expectNoHorizontalOverflow(page);
  await expectSheetTapTargets(sheet);

  // And the whole round trip works by touch alone.
  await page.getByTestId("voice-save").tap();
  await expect(page.getByTestId("voice-save")).toHaveCount(0, { timeout: 15_000 });
  await expect(row).toContainText("Calm and reassuring, never pushy.");

  // Put the demo tenant back where the seed left it.
  await row.tap();
  await page.getByTestId("voice-warm_casual").tap();
  await page.getByTestId("voice-save").tap();
  await expect(page.getByTestId("voice-save")).toHaveCount(0, { timeout: 15_000 });
  await expect(row).toContainText("Warm and casual");
});
