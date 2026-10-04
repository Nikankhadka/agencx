/**
 * Ticket 24: the desktop overlay standard.
 *
 * At `lg+` (1024px and up) every `Sheet` becomes a centered, height-capped
 * dialog: forms cap at `max-w-md` (448px), document surfaces at `--width-doc`
 * (768px). Below `lg` every sheet keeps today's bottom pull-up. `Modal` caps
 * at `calc(100vh-2rem)` with an internal scroll area so a tall editor stays
 * inside the viewport.
 *
 * The spec runs under the default `chromium` project (Desktop Chrome 1280 -
 * the mobile project only claims `mobile*.spec.ts`), so the mobile half sets
 * its own 390px viewport rather than relying on a second project.
 *
 * The panel animates with the CSS `translate` property, so a computed
 * `transform` poll is identity on the first frame - wait past
 * `--duration-push` (280ms) before measuring, per `.agents/memory.md`.
 */

import { expect, test, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";
import { draftRecord, recordsStore, stubRecords } from "./knowledge-review-mocks";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;
const DESKTOP = { width: 1280, height: 720 };
const MOBILE = { width: 390, height: 844 };

/** Past `--duration-push` (280ms) plus headroom. */
async function settlePush(page: Page): Promise<void> {
  await page.waitForTimeout(700);
}

/** Open the Edit ABN & Tax form sheet from Business details. */
async function openAbnSheet(page: Page) {
  await page.goto("/business/details");
  await page.getByRole("button", { name: /ABN & Tax/ }).click();
  const dialog = page.getByRole("dialog", { name: "Edit ABN & Tax" });
  await expect(dialog).toBeVisible();
  await settlePush(page);
  return dialog;
}

test.describe("desktop overlay standard (1280)", () => {
  test.use({ viewport: DESKTOP });

  test("a form sheet is a centered, content-sized dialog", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    const dialog = await openAbnSheet(page);

    const box = (await dialog.boundingBox())!;
    const viewport = page.viewportSize()!;

    // Forms cap at max-w-md and are shorter than the viewport.
    expect(box.width).toBeLessThanOrEqual(448);
    expect(box.height).toBeLessThan(viewport.height);

    // Centered: the root's `justify-center` puts the panel's centre at 640.
    const centerX = box.x + box.width / 2;
    expect(Math.abs(centerX - viewport.width / 2)).toBeLessThanOrEqual(2);
  });

  test("the knowledge review is a wider document dialog", async ({ page, request }) => {
    const store = recordsStore([
      draftRecord({ id: "saved-1", filename: "hours.txt", status: "ready" }),
    ]);
    await stubRecords(page, store);

    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/details/knowledge");

    const saved = page.locator("article").filter({ hasText: "hours.txt" });
    await expect(saved).toBeVisible();
    await saved.getByTestId("knowledge-edit").click();

    const dialog = page.getByRole("dialog", { name: "Edit what I know" });
    await expect(dialog).toBeVisible();
    await settlePush(page);

    const box = (await dialog.boundingBox())!;
    expect(box.width).toBeLessThanOrEqual(768);
  });

  test("a tall offering modal caps at the viewport and scrolls its body", async ({
    page,
    request,
  }) => {
    // A short desktop viewport (still >= lg wide) forces the tall editor past
    // the panel's `calc(100vh-2rem)` cap - US-3's "short viewport" case.
    await page.setViewportSize({ width: 1280, height: 360 });
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/offerings");

    await page.getByTestId("offering-edit").first().click();
    const dialog = page.getByRole("dialog", { name: "Edit offering" });
    await expect(dialog).toBeVisible();
    // Expand the optional details so the body is reliably taller than the cap.
    await dialog.locator("summary", { hasText: "Add details" }).click();

    const box = (await dialog.boundingBox())!;
    const viewport = page.viewportSize()!;
    expect(box.height).toBeLessThanOrEqual(viewport.height);

    // The title stays fixed and the body is the scroll container.
    const body = dialog.locator("div").first();
    expect(await body.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);
  });
});

test.describe("mobile overlay standard (390)", () => {
  test.use({ viewport: MOBILE });

  test("a form sheet stays bottom-anchored and full-width", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    const dialog = await openAbnSheet(page);

    const box = (await dialog.boundingBox())!;
    const viewport = page.viewportSize()!;

    // Bottom edge equals the viewport height (bottom-anchored).
    expect(Math.abs(box.y + box.height - viewport.height)).toBeLessThanOrEqual(1);
    // Full width: the panel spans the viewport (fixed root is `inset-0`).
    expect(Math.abs(box.width - viewport.width)).toBeLessThanOrEqual(1);
  });
});
