import { test } from "@playwright/test";
import { loginInChat } from "./auth-helpers";

/**
 * Not a regression test - a screenshot driver for the W-7 walkthrough fixes,
 * run against the real backend and LLM with a fresh (never-onboarded) email so
 * the interview starts at its opening beat. Saved into e2e/screenshots/.
 */

const SHOTS = "e2e/screenshots";

async function waitIdle(page: import("@playwright/test").Page) {
  // The composer is re-enabled (busy=false) once a turn settles.
  await page
    .getByTestId("onboarding-composer")
    .waitFor({ state: "visible", timeout: 30_000 })
    .catch(() => {});
  await page.waitForTimeout(4500);
}

async function say(page: import("@playwright/test").Page, text: string) {
  const pill = page.getByRole("textbox").first();
  await pill.click();
  await pill.fill(text);
  await pill.press("Enter");
  await waitIdle(page);
}

test("W-7 walkthrough screenshots", async ({ page, request }) => {
  test.setTimeout(300_000);
  const email = `w7-${Date.now()}@founder.dev`;
  await loginInChat(page, request, email);
  await page.waitForURL("**/onboarding");
  await waitIdle(page);

  // Fix 1/2: opening asks for the owner's name, and there is no skip chip.
  await page.screenshot({ path: `${SHOTS}/01-opening.png`, fullPage: true });

  // Fix 3: junk name is challenged, the same beat is asked again.
  await say(page, "34234234");
  await page.screenshot({ path: `${SHOTS}/02-junk-name-rejected.png`, fullPage: true });

  // A real answer is accepted and the interview advances.
  await say(page, "Nikan");
  await page.screenshot({ path: `${SHOTS}/03-name-accepted.png`, fullPage: true });

  // Walk the required beats to reach a chip beat and then go-live.
  await say(page, "Sababa");
  await say(page, "a pita and coffee cafe");
  // headcount beat carries chips - screenshot the chips present.
  await page.screenshot({ path: `${SHOTS}/04-headcount-chips.png`, fullPage: true });
  // Fix 6: tapping a chip removes the whole row while the turn is in flight.
  await page.getByTestId("onboarding-chip-just me").click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${SHOTS}/04b-chip-gone-while-busy.png`, fullPage: true });
  await waitIdle(page);
  await say(page, "9 to 5, Monday to Friday");
  await say(page, "pita, coffee, wraps");
  // contact beat: the owner-email + Phone number chips are still offered.
  await page.screenshot({ path: `${SHOTS}/04c-contact-chips.png`, fullPage: true });
  await say(page, "hello@sababa.dev");
  await say(page, "no");

  // Fix 7: upload a small menu at the knowledge stage and open the review sheet,
  // to capture the priced offering cards (name + price on a row, description
  // beneath) with the document's offering/price text NOT shown as raw sections.
  const menu = [
    "Sababa menu",
    "",
    "What we offer",
    "Falafel wrap - a warm pita with house falafel and tahini - $12",
    "Flat white - our own blend - $5",
    "",
    "Hours",
    "9 to 5, Monday to Friday",
  ].join("\n");
  await page.getByTestId("onboarding-file-input").setInputFiles({
    name: "menu.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(menu),
  });
  const reviewSave = page.getByTestId("onboarding-knowledge-save");
  await reviewSave.waitFor({ timeout: 60_000 }).catch(() => {});
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${SHOTS}/06-review-sheet-cards.png`, fullPage: true });
  await reviewSave.click().catch(() => {});
  await waitIdle(page);

  // Keep saying "skip"/"no" until the go-live address field appears - the model
  // sometimes needs an extra turn to resolve the ABN and knowledge asks.
  const slug = page.getByTestId("onboarding-public-slug");
  for (let i = 0; i < 6; i++) {
    if (await slug.isVisible().catch(() => false)) break;
    await say(page, "skip");
  }

  // Fix 5: go-live shows only the address, prefilled, with a read-back line.
  await slug.waitFor({ timeout: 30_000 }).catch(() => {});
  await page.screenshot({ path: `${SHOTS}/05-go-live-address-only.png`, fullPage: true });
});
