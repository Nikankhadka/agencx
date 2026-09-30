/**
 * E2E guard for the product's copy rules (B-1, PRD section 13).
 *
 * Two rules, one sweep:
 *   1. The product is Agencx. "Wren" is the repo, the roles and the env keys -
 *      it must never reach a screen.
 *   2. User-facing copy never says "AI", "agent", "automated" or "virtual".
 *      These sell the mechanism; the copy should sell what the business gets.
 *      W-9's copy-rule amendment (13-walkthrough.md, Amendment 3) took
 *      "assistant" off that list and put "virtual" on it: both mandated
 *      openings name the assistant as what the surface is, and a noun the
 *      surface cannot use is a surface that cannot say what it is. Answering a
 *      direct "are you human?" honestly was never covered by this sweep and
 *      still is not - that lives in the customer contract's own tests.
 *
 * Scope is deliberate. Every surface here renders text the code owns. Two are
 * excluded and neither is an oversight: /chats renders historical customer
 * conversations (including turns written before these rules existed - a
 * re-seed changes the fixture, not the code), and /onboarding renders live
 * model prose. Guarding either would be testing data, and would go red for
 * reasons no commit caused.
 */

import { test, expect, type Page } from "@playwright/test";
import {
  DEMO_USERS,
  loginAsTenantAdmin,
  loginAsPlatformAdmin,
} from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;
const FOUNDER = DEMO_USERS.find((u) => u.surface === "platform")!;

const BANNED: { label: string; pattern: RegExp }[] = [
  // Case-sensitive and word-bounded: "AI" is a substring of email, detail,
  // available, again - a loose match here would fail on ordinary English.
  { label: "AI", pattern: /\bAI\b/ },
  { label: "agent", pattern: /\bagents?\b/i },
  { label: "automated", pattern: /\bautomat(ed|ic|ically|ion)\b/i },
  { label: "virtual", pattern: /\bvirtual\b/i },
  { label: "Wren", pattern: /\bwren\b/i },
];

async function expectCleanCopy(page: Page, where: string) {
  // innerText, not textContent: the latter drags in Next's dev-mode RSC
  // payload, which names components the customer never sees.
  const visible = await page.locator("body").innerText();
  for (const { label, pattern } of BANNED) {
    const hit = visible.match(pattern);
    expect(hit?.[0] ?? null, `"${label}" reached ${where}: ...${hit ? visible.slice(Math.max(0, (hit.index ?? 0) - 60), (hit.index ?? 0) + 60) : ""}...`).toBeNull();
  }
}

test.describe("copy rules - the customer's side", () => {
  test("the public page says nothing about the mechanism", async ({ page }) => {
    await page.goto("/bytefix");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectCleanCopy(page, "the public page");
  });

  test("the browser tab is Agencx", async ({ page }) => {
    await page.goto("/bytefix");
    // The tenant surface is branded by the tenant, but the document title is
    // the product's and used to read "Wren".
    await expect(page).toHaveTitle(/Agencx/);
  });
});

test.describe("copy rules - the owner's side", () => {

  for (const path of [
    "/home",
    "/business",
    "/business/page",
    "/business/offerings",
    "/business/details",
  ]) {
    test(`${path} is clean`, async ({ page, request }) => {
      await loginAsTenantAdmin(page, request, BYTEFIX);
      await page.goto(path);
      await expect(page.getByRole("navigation", { name: "Console" })).toBeVisible();
      await expectCleanCopy(page, path);
    });
  }
});

test.describe("copy rules - shared components", () => {
  test("the shared confirm dialog and a toast stay clean", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");

    // The "website" slot, not "instagram" - business-hub.spec.ts already
    // exercises that one and these specs share one seeded tenant.
    const tile = page.getByTestId("booking-platform-website");
    await tile.click();
    if (await page.getByTestId("booking-link-remove").isVisible()) {
      await page.getByTestId("booking-link-remove").click();
      await page.getByTestId("confirm-accept").click();
      await expect(tile).toContainText("Add");
      await tile.click();
    }

    await page.getByTestId("booking-link-input").fill("bytefix.example.com");
    await page.getByTestId("booking-link-save").click();
    await expect(page.getByText("Link saved", { exact: true })).toBeVisible();
    await expectCleanCopy(page, "the link-saved toast");

    // Put the slot back, and check the shared ConfirmDialog (U-3) on the way -
    // open and unconfirmed, so its own copy is swept before it closes.
    await tile.click();
    await page.getByTestId("booking-link-remove").click();
    await expect(page.getByTestId("confirm-accept")).toBeVisible();
    await expectCleanCopy(page, "the shared confirm dialog");
    await page.getByTestId("confirm-accept").click();
    await expect(tile).toContainText("Add");
    await expect(page.getByText("Link removed", { exact: true })).toBeVisible();
    await expectCleanCopy(page, "the link-removed toast");
  });
});

test.describe("copy rules - the platform surface", () => {

  test("the platform chrome is Agencx, not Wren", async ({ page }) => {
    await loginAsPlatformAdmin(page, FOUNDER);
    await expect(page.getByText("Agencx").first()).toBeVisible();
    await expectCleanCopy(page, "the platform surface");
  });
});
