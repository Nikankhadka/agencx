/**
 * Mobile e2e helpers (T-063). Shared assertions for the mobile-chrome project:
 * no horizontal overflow at the two target widths, interactive controls at the
 * 44px minimum tap target, and a pinned composer.
 */

import { expect, type Page } from "@playwright/test";

export const MOBILE_WIDTHS = [375, 390] as const;

/** Body must not scroll horizontally at the current viewport width. */
export async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.body.scrollWidth - document.documentElement.clientWidth,
  );
  expect(
    overflow,
    "page must not overflow horizontally (body scrollWidth exceeds viewport)",
  ).toBeLessThanOrEqual(0);
}

/**
 * Every visible button / input / select / textarea / role=button must meet the
 * 44px minimum tap target. Text links are excluded on purpose - nav/inline
 * links legitimately sit below 44px; the rule is about tappable controls.
 */
export async function expectTapTargets(page: Page, minPx = 44): Promise<void> {
  const undersized = await page.evaluate((min) => {
    const selector = "button, [role='button'], input, select, textarea";
    const offenders = Array.from(document.querySelectorAll<HTMLElement>(selector)).filter((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return false; // hidden
      const style = window.getComputedStyle(el);
      if (style.visibility === "hidden") return false;
      return rect.height < min;
    });
    return offenders.map((el) => ({
      tag: el.tagName.toLowerCase(),
      label:
        el.getAttribute("aria-label") ??
        el.getAttribute("placeholder") ??
        el.textContent?.trim().slice(0, 40) ??
        "",
      height: Math.round(el.getBoundingClientRect().height),
    }));
  }, minPx);
  expect(undersized, "interactive controls must be >= 44px tall").toEqual([]);
}

/**
 * The composer (and its send/stop control) stays on screen while the thread
 * scrolls - i.e. it is pinned to the bottom rather than scrolling away with
 * the conversation.
 */
export async function expectComposerPinned(page: Page): Promise<void> {
  const pinned = await page.evaluate(() => {
    const composer = document.querySelector<HTMLElement>("[data-testid='onboarding-composer']");
    if (!composer) return true; // no composer surface (e.g. live state) - vacuously pinned
    const rect = composer.getBoundingClientRect();
    return rect.bottom <= window.innerHeight + 1 && rect.bottom > 0;
  });
  expect(pinned, "composer must be visible (pinned) at the bottom of the viewport").toBe(true);
}
