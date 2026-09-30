import fs from "fs";
import path from "path";
import { test, expect, type Page } from "@playwright/test";

/**
 * Throwaway evidence-capture spec for the founder walkthrough of tickets
 * 19 (intent and identity), 20 (required services) and 12 (the
 * onboarding-normalization slice plus Part 3 U-1..U-4) on the live preview
 * deploy. Not part of the regression suite - excluded in
 * playwright.config.ts's testIgnore, same as w7-screenshots.spec.ts and
 * w9-repro.spec.ts.
 *
 * Runs against E2E_BASE_URL (the preview origin), which shares the
 * production Supabase database (see docs/agencx/evidence/walkthrough-2026-10/
 * README.md for the full safety notes). Every identity this spec creates
 * uses a `wt-` prefixed slug/name; every bytefix conversation it creates is
 * printed to the console and logged in that README.
 *
 * Login bypasses email delivery (not configured for arbitrary addresses on
 * preview) via GoTrue's admin `generate_link` endpoint, reading
 * SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY from the environment - source
 * .env.deploy.local before running this spec. No secret is ever logged.
 */

const SHOTS = path.resolve(__dirname, "..", "..", "docs", "agencx", "evidence", "walkthrough-2026-10");
fs.mkdirSync(SHOTS, { recursive: true });

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 }; // viewport-only approximation of iPhone 13, not full device emulation

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required - source .env.deploy.local before running this spec`);
  return value;
}

const SUPABASE_URL = requireEnv("SUPABASE_URL");
const SERVICE_ROLE_KEY = requireEnv("SUPABASE_SERVICE_ROLE_KEY");

async function shot(page: Page, name: string) {
  // Viewport-only, not fullPage: this app always mounts its Sheet dialogs
  // (position: fixed, translated off-screen while closed) rather than
  // conditionally rendering them, and Chromium's full-page stitching paints
  // a closed, off-screen Sheet into the stitched image anyway - a capture
  // artifact, not a real second panel. Viewport-only also matches what a
  // founder reviewing this on their own screen would actually see.
  await page.screenshot({ path: path.join(SHOTS, name) });
}

// ---------------------------------------------------------------------------
// Preview login (GoTrue admin API stands in for email delivery)
// ---------------------------------------------------------------------------

async function fetchPreviewOtp(email: string): Promise<string> {
  const res = await fetch(`${SUPABASE_URL}/auth/v1/admin/generate_link`, {
    method: "POST",
    headers: {
      apikey: SERVICE_ROLE_KEY,
      Authorization: `Bearer ${SERVICE_ROLE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ type: "magiclink", email }),
  });
  if (!res.ok) throw new Error(`generate_link failed: ${res.status} ${await res.text()}`);
  const data = (await res.json()) as { email_otp?: string; properties?: { email_otp?: string } };
  const otp = data.email_otp ?? data.properties?.email_otp;
  if (!otp) throw new Error("generate_link response carried no email_otp");
  return otp;
}

/**
 * Logs in through the real /login UI. Clicking "Send" first creates a real
 * (undelivered) OTP via signInWithOtp; the admin `generate_link` call right
 * after issues a fresh one that supersedes it (GoTrue keeps one live code
 * per address), which is what actually gets typed in.
 */
async function loginPreview(page: Page, email: string): Promise<void> {
  await page.goto("/login");
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByRole("button", { name: "Send" }).click();
  await page.getByLabel("Digit 1").waitFor({ timeout: 15_000 });
  const otp = await fetchPreviewOtp(email);
  for (let i = 0; i < 6; i++) {
    await page.getByLabel(`Digit ${i + 1}`).fill(otp[i]);
  }
  await page.waitForURL(/\/(onboarding|home)/, { timeout: 30_000 });
}

// ---------------------------------------------------------------------------
// Onboarding thread helpers (adapted from e2e/w9-repro.spec.ts)
// ---------------------------------------------------------------------------

async function onboardingIdle(page: Page) {
  await page
    .getByTestId("onboarding-composer")
    .waitFor({ state: "visible", timeout: 30_000 })
    .catch(() => {});
  await page.waitForTimeout(3500);
}

async function onboardingThreadText(page: Page): Promise<string> {
  return (await page.getByTestId("onboarding-thread").innerText()).trim();
}

async function onboardingSettle(page: Page, deadlineMs = 60_000): Promise<string> {
  const start = Date.now();
  let last = "";
  while (Date.now() - start < deadlineMs) {
    const text = await onboardingThreadText(page);
    if (text === last && text.length > 0) return text;
    last = text;
    await page.waitForTimeout(1500);
  }
  return last;
}

async function onboardingSay(page: Page, text: string) {
  const pill = page.getByRole("textbox").first();
  await pill.click();
  await pill.fill(text);
  await pill.press("Enter");
  await onboardingIdle(page);
  await onboardingSettle(page);
}

async function onboardingChip(page: Page, value: string) {
  await page.getByTestId(`onboarding-chip-${value}`).click();
  await onboardingIdle(page);
  await onboardingSettle(page);
}

async function onboardingChipByLabel(page: Page, label: string) {
  await page.getByRole("button", { name: label, exact: true }).click();
  await onboardingIdle(page);
  await onboardingSettle(page);
}

// ---------------------------------------------------------------------------
// Customer chat helpers
// ---------------------------------------------------------------------------

/**
 * The storefront's chat lives in a Sheet (bottom drawer on mobile, inset
 * panel on desktop) that starts translated fully off-screen and is opened by
 * the round "Chat with {name}" launcher in the header - CustomerChat is
 * always mounted, just not visible, so the Message input exists in the DOM
 * before this click and is merely out of the viewport.
 */
async function openCustomerChat(page: Page) {
  await page.getByRole("button", { name: /^Chat with/ }).click();
  await page.getByLabel("Message").waitFor({ state: "visible", timeout: 10_000 });
}

async function customerSay(page: Page, text: string) {
  const input = page.getByLabel("Message");
  await input.click();
  await input.fill(text);
  await page.getByRole("button", { name: "Send" }).click();
  // The composer disables (busy=true) for the duration of the streamed
  // reply and re-enables once the turn's `done` event lands.
  await expect(input).toBeEnabled({ timeout: 90_000 });
  await page.waitForTimeout(500);
}

test.describe.configure({ mode: "serial" });

// ===========================================================================
// Ticket 19: intent and identity - pricing question, human request, name-only
// contact capture, non-terminal handoff, owner-side visibility.
// ===========================================================================

test("ticket 19 - pricing question, handoff, name-only contact, non-terminal", async ({ page }) => {
  test.setTimeout(600_000);

  await page.setViewportSize(DESKTOP);
  await page.goto("/bytefix");
  await shot(page, "01-t19-storefront-opening-desktop.png");

  await openCustomerChat(page);
  await shot(page, "01b-t19-chat-opened-desktop.png");

  await customerSay(page, "How much does a cracked screen repair cost?");
  await shot(page, "02-t19-pricing-reply-desktop.png");

  await customerSay(page, "I'd like to speak to a real person about this, please.");
  const bodyAfterHandoff = await page.locator("main").innerText();
  expect(bodyAfterHandoff).toContain("forwarded your query");
  await shot(page, "03-t19-handoff-contact-ask-desktop.png");

  // Name only - never a phone/email nudge, never a re-ask.
  await customerSay(page, "Jordan");
  await shot(page, "04-t19-name-only-accepted-desktop.png");

  // The conversation is not terminal: the composer stays present and usable,
  // and the "someone will take it from here" banner (the tenant-limit stop)
  // never appears.
  await expect(page.getByLabel("Message")).toBeEnabled();
  await expect(page.getByText("Someone from the business will take it from here.")).toHaveCount(0);
  await customerSay(page, "Are you still there? I have another question.");
  await shot(page, "05-t19-continues-after-handoff-desktop.png");

  await page.setViewportSize(MOBILE);
  await page.waitForTimeout(300);
  await shot(page, "06-t19-thread-mobile.png");
  await page.setViewportSize(DESKTOP);

  // Owner side: log in as the bytefix owner and open the new conversation.
  const owner = await page.context().browser()!.newPage();
  await loginPreview(owner, "owner@bytefix.dev");
  await owner.goto("/chats");
  await owner.getByTestId("chat-row").first().waitFor({ state: "visible" });
  await shot(owner, "07-t19-owner-chats-list-desktop.png");
  await owner.getByTestId("chat-row").first().click();
  await owner.waitForURL(/\/chats\/[^/]+$/);
  const conversationId = owner.url().split("/chats/")[1];
  console.log(`WALKTHROUGH_CONVERSATION_ID=${conversationId}`);
  // The thread loads its transcript via its own fetch after the route change,
  // not before it - wait for a message that is always there, so the shot
  // below is the loaded thread rather than a still-empty pane.
  await owner.getByText("How much does a cracked screen repair cost?").waitFor({ state: "visible", timeout: 15_000 });
  await shot(owner, "08-t19-owner-thread-name-desktop.png");
  await owner.close();
});

// ===========================================================================
// Ticket 20 (required services) + ticket 12 onboarding-normalization slice +
// Part 3 U-1..U-4, all walked through in one fresh wt- onboarding run.
// ===========================================================================

test("ticket 20 and 12 - onboarding, services overview, normalization, U-1..U-4", async ({ page }) => {
  test.setTimeout(900_000);

  const stamp = Date.now();
  const email = `wt-walkthrough+${stamp}@agencx.test`;
  console.log(`WALKTHROUGH_WT_EMAIL=${email}`);

  await page.setViewportSize(DESKTOP);
  await loginPreview(page, email);
  await page.waitForURL("**/onboarding");
  await onboardingIdle(page);
  await shot(page, "10-t20-opening-owner-name-ask-desktop.png");

  // Owner name - proposal, not assumption (12: name-proposal confirmation).
  await onboardingSay(page, "Robin Walker");
  await shot(page, "11-t12-owner-name-proposal-confirm-desktop.png");
  await onboardingChip(page, "yes");

  // Business name - same proposal/confirm seam, and its slug is the wt- proof.
  await onboardingSay(page, "WT Walkthrough Cafe");
  await shot(page, "12-t12-business-name-proposal-confirm-desktop.png");
  await onboardingChip(page, "yes");

  await onboardingSay(page, "a small neighborhood cafe");

  await shot(page, "13-t20-headcount-chips-desktop.png");
  await onboardingChip(page, "just me");

  await onboardingSay(page, "9 to 5, Monday to Friday");

  // 20: services is required, free text, price-inclusive, and carries no
  // Skip chip anywhere in this beat.
  await expect(page.getByTestId(/onboarding-chip-skip/)).toHaveCount(0);
  await shot(page, "14-t20-services-ask-no-skip-chip-desktop.png");
  await onboardingSay(page, "Drip coffee, $4 to $6. Pastries, $3 to $6.");
  await shot(page, "15-t20-services-answered-desktop.png");

  await shot(page, "16-t20-voice-chips-desktop.png");
  await onboardingChipByLabel(page, "Warm and casual");

  await onboardingSay(page, "0412 345 678");

  await onboardingChip(page, "none"); // ABN: No (NO_ABN sentinel) - also resolves GST

  // Knowledge ask: the one Skip chip left in the whole interview, always visible.
  await shot(page, "17-t20-knowledge-ask-single-skip-chip-desktop.png");
  await onboardingChip(page, "skip");

  await shot(page, "18-t20-readiness-confirm-wt-slug-desktop.png");
  const proposedSlug = await page.getByTestId("onboarding-public-slug").inputValue();
  expect(proposedSlug.startsWith("wt-")).toBeTruthy();

  // The business name is the same fixed text on every run of this spec, so
  // the proposed slug collides with an earlier run's still-present tenant.
  // Make it unique before confirming instead of relying on the "already
  // taken" retry path (the screenshot above still shows the natural
  // proposal, unedited).
  const slugValue = `${proposedSlug}-${stamp}`;
  await page.getByTestId("onboarding-public-slug").fill(slugValue);
  console.log(`WALKTHROUGH_WT_SLUG=${slugValue}`);

  await page.getByTestId("onboarding-confirm").click();
  await page.waitForURL(/\/home/, { timeout: 30_000 });

  // U-3: the shared confirm dialog (sign-out), cancelled to keep the session.
  await page.getByRole("button", { name: "Sign out" }).click();
  await shot(page, "19-u3-signout-confirm-dialog-desktop.png");
  await page.getByRole("button", { name: "Cancel" }).click();

  // 20: Home's greeting fallback chain (owner name here; business name and
  // "admin" are the same chain, verified by reading
  // frontend/src/app/(tenant-admin)/(console)/home/page.tsx:51-55 rather than
  // a second onboarding run, to avoid creating a second wt- tenant for a
  // branch that is not reachable without deliberately leaving the name blank).
  await page.waitForTimeout(500);
  await shot(page, "20-t20-home-greeting-desktop.png");
  await page.setViewportSize(MOBILE);
  await page.waitForTimeout(300);
  await shot(page, "21-t20-home-greeting-mobile.png"); // U-1: mobile tab bar nav idiom
  await page.setViewportSize(DESKTOP);

  // Owner's own preview of the storefront: ServicesOverview reads the
  // `services` answer back verbatim, since the offerings catalog is empty.
  await page.goto("/business/page");
  await page.waitForTimeout(500);
  await shot(page, "22-t20-business-preview-services-overview-desktop.png");
  await expect(page.getByTestId("services-overview")).toContainText("Drip coffee");

  // Public storefront: the same component, same text.
  const publicPage = await page.context().browser()!.newPage();
  await publicPage.setViewportSize(DESKTOP);
  await publicPage.goto(`/${slugValue}`);
  await publicPage.waitForTimeout(500);
  await shot(publicPage, "23-t20-public-storefront-services-overview-desktop.png");
  await expect(publicPage.getByTestId("services-overview")).toContainText("Drip coffee");
  await publicPage.setViewportSize(MOBILE);
  await publicPage.waitForTimeout(300);
  await shot(publicPage, "24-t20-public-storefront-services-overview-mobile.png");
  await publicPage.setViewportSize(DESKTOP);

  // 12: offering candidates stay private/pending until reviewed. A post-launch
  // knowledge upload, not part of onboarding, so the "nothing priced" screens
  // above stay valid evidence of the empty-catalog state.
  await page.goto("/business/details/knowledge");
  const menu = [
    "WT Walkthrough Cafe menu",
    "",
    "What we offer",
    "Drip coffee - a rotating single origin - $5",
    "Butter croissant - baked daily - $4",
  ].join("\n");
  await page.getByTestId("knowledge-file-input").setInputFiles({
    name: "menu.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(menu),
  });
  // The upload flow opens the ReviewSheet itself the moment the draft is
  // ready (business/details/knowledge/page.tsx's addFile), in the same beat
  // as the toast - no separate click needed.
  await expect(page.getByText("Draft ready to review")).toBeVisible({ timeout: 60_000 });
  await shot(page, "25-t12-knowledge-upload-toast-desktop.png");

  await page.waitForTimeout(1500);
  await shot(page, "26-t12-review-sheet-candidates-private-desktop.png");

  // Still nothing public while the review sheet is open and unsaved.
  await publicPage.goto(`/${slugValue}`);
  await publicPage.waitForTimeout(500);
  await shot(publicPage, "27-t12-storefront-still-no-offerings-desktop.png");
  await expect(publicPage.getByTestId("services-overview")).toBeVisible();

  await page.getByTestId("knowledge-save").click();
  await expect(page.getByText("Saved")).toBeVisible({ timeout: 60_000 });
  await shot(page, "28-t12-review-sheet-save-toast-desktop.png");

  await publicPage.goto(`/${slugValue}`);
  await publicPage.waitForTimeout(500);
  await shot(publicPage, "29-t12-storefront-offerings-now-public-desktop.png");

  await publicPage.close();
});
