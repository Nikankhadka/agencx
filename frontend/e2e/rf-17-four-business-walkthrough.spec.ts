/**
 * E2E for RF-17 (Slice 2): the assembled four-business walkthrough.
 *
 * Surface: all three - the public storefront (`/{slug}`), the customer chat
 * opened from it, the owner console queue (`/chats`), and the console business
 * hub (`/business`).
 *
 * The point is the platform claim, not any one screen: four structurally
 * different businesses (bytefix retail/repair, lumident dental, sababa cafe,
 * wellspring general clinic) run on identical code and differ only by
 * `tenant_config` + seeded catalog. This spec drives the SAME code over all
 * four and asserts the config-driven differences per business - its own name,
 * greeting and starter questions, its own offerings and price formatting, and
 * its own conversation references in the queue.
 *
 * Deterministic: the customer-chat turn is stubbed through `page.route` with
 * that business's own catalog content (RF-9/RF-12's pattern), the live model is
 * never on the path, and the queue reads the tenant's own seeded conversations.
 *
 * Screenshots are OPT-IN via `RF17_CAPTURE=1`, so CI (which runs this spec as
 * part of the regression suite in `make test-e2e`) never rewrites tracked
 * files. When capture is on, they land viewport-only (never `fullPage`: the
 * app keeps its chat Sheet mounted off-screen, and full-page stitching paints
 * a closed overlay into the image - see `walkthrough-2026-10.spec.ts`).
 */

import fs from "fs";
import path from "path";
import { test, expect, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const CAPTURE = process.env.RF17_CAPTURE === "1";
const SHOTS_DIR =
  process.env.RF17_SHOTS_DIR ??
  path.resolve(__dirname, "..", "..", "docs", "agencx", "evidence", "rf-17-2026-10-03");
if (CAPTURE) fs.mkdirSync(SHOTS_DIR, { recursive: true });

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 }; // viewport-only approximation of iPhone 13

/** Viewport-only capture, opt-in. A no-op when RF17_CAPTURE is unset. */
async function shot(page: Page, name: string) {
  if (!CAPTURE) return;
  await page.screenshot({ path: path.join(SHOTS_DIR, name) });
}

/**
 * Hide Next.js's dev-tools indicator (a `<nextjs-portal>` custom element pinned
 * to the bottom-left of every local dev page). It is not part of the app and
 * overlaps a price row on the mobile storefront capture, so captures hide it.
 * Registered only under RF17_CAPTURE, and before the first navigation, so with
 * capture off the page is never touched and no assertion sees this.
 */
async function hideDevIndicator(page: Page): Promise<void> {
  if (!CAPTURE) return;
  await page.addInitScript(() => {
    document.addEventListener("DOMContentLoaded", () => {
      const style = document.createElement("style");
      style.textContent = "nextjs-portal{display:none!important}";
      document.head.appendChild(style);
    });
  });
}

const sse = (...events: object[]) =>
  events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");

interface BusinessCase {
  /** Descriptor used in the named test title, matching the ticket's wording. */
  label: string;
  slug: string;
  /** The public display name (`brand.display_name`) the storefront and chat use. */
  name: string;
  ownerEmail: string;
  /** The part of the configured greeting the identity-line normalizer keeps. */
  greetingAdd: string;
  starters: [string, string, string];
  /** An offering that appears on this business's page and nowhere else's. */
  uniqueOffering: string;
  /** This tenant's own seeded `conversations.customer_ref` values. */
  ownRefs: string[];
  /** The card payload drawn from this business's own catalog. */
  card: { itemLabel: string; priceCents: number; priceText: string };
}

const BUSINESSES: BusinessCase[] = [
  {
    label: "retail/repair",
    slug: "bytefix",
    name: "Bytefix Repairs",
    ownerEmail: "owner@bytefix.dev",
    greetingAdd: "I can quote a repair",
    starters: [
      "How much is a screen replacement?",
      "What's the status of my repair?",
      "How long do repairs usually take?",
    ],
    uniqueOffering: "iPhone 11 (Refurbished, 64GB)",
    ownRefs: ["alex.rivera", "jordan.patel"],
    card: {
      itemLabel: "iPhone 11 (Refurbished, 64GB)",
      priceCents: 24900,
      priceText: "$249.00",
    },
  },
  {
    label: "dental",
    slug: "lumident",
    name: "Lumident Dental",
    ownerEmail: "owner@lumident.dev",
    greetingAdd: "I can help you understand a treatment",
    starters: [
      "How much is a standard cleaning?",
      "What does a tooth-colored filling cost?",
      "Do you take walk-in emergencies?",
    ],
    uniqueOffering: "Dental Crown",
    ownRefs: ["patient.a", "patient.b"],
    card: {
      itemLabel: "Dental Crown",
      priceCents: 110000,
      priceText: "$1,100.00",
    },
  },
  {
    label: "cafe",
    slug: "sababa",
    name: "Sabbaba",
    ownerEmail: "owner@sababa.dev",
    greetingAdd: "I can walk you through the menu",
    starters: [
      "How much is the Super Plate?",
      "What comes in the Sabbaba Pita Pocket?",
      "When are you open?",
    ],
    uniqueOffering: "Super Plate",
    ownRefs: ["diner.a", "diner.b"],
    card: {
      itemLabel: "Super Plate",
      priceCents: 3700,
      priceText: "$37.00",
    },
  },
  {
    label: "general clinic",
    slug: "wellspring",
    name: "Wellspring Medical Centre",
    ownerEmail: "owner@wellspring.dev",
    greetingAdd: "answer questions about our services and fees",
    starters: [
      "How much is a standard consultation?",
      "Are childhood vaccinations free?",
      "How do I get my test results?",
    ],
    uniqueOffering: "Skin Check",
    ownRefs: ["patient.c", "patient.d"],
    card: {
      itemLabel: "Standard Consultation",
      priceCents: 8500,
      priceText: "$85.00",
    },
  },
];

const ALL_REFS = BUSINESSES.flatMap((b) => b.ownRefs);

/** The streamed reply, carrying this business's own price summary and catalog. */
function cardTurn(business: BusinessCase): string {
  const { itemLabel, priceCents } = business.card;
  return sse(
    { type: "conversation", conversation_id: "11111111-1111-4111-8111-111111111111" },
    {
      type: "price_summary",
      summary: {
        line_items: [
          {
            kind: "item",
            item_id: business.slug,
            label: itemLabel,
            quantity: 1,
            unit_amount_cents: priceCents,
            line_total_cents: priceCents,
          },
        ],
        subtotal_cents: priceCents,
        tax_cents: 0,
        total_cents: priceCents,
        disclaimer: "Based on the business's current confirmed prices.",
      },
    },
    {
      type: "catalog",
      catalog: {
        offerings: [
          {
            id: business.slug,
            name: itemLabel,
            description: `From ${business.name}'s own catalog`,
            category: null,
            price_cents: priceCents,
          },
        ],
      },
    },
    { type: "token", text: `Here is ${business.name}'s pricing.` },
    { type: "done" },
  );
}

test.describe("RF-17 four-business walkthrough", () => {
  for (const business of BUSINESSES) {
    const chatButton = `Chat with ${business.name}`;
    const title =
      `RF-17 ${business.slug} (${business.label}) - ` +
      "config-driven storefront, chat, queue, and business hub";

    test(title, async ({ page, request }) => {
      test.setTimeout(180_000);
      await hideDevIndicator(page);
      await page.setViewportSize(DESKTOP);

      // --- 1. Public storefront, anonymous -------------------------------
      await page.goto(`/${business.slug}`);
      await expect(async () => {
        await expect(page.getByRole("heading", { level: 1 })).toContainText(business.name);
      }).toPass({ timeout: 15_000 });
      await expect(page.getByRole("main")).toContainText(business.uniqueOffering);
      await page.waitForTimeout(300);
      await shot(page, `01-${business.slug}-storefront-desktop.png`);

      await page.setViewportSize(MOBILE);
      await page.waitForTimeout(300);
      await shot(page, `02-${business.slug}-storefront-mobile.png`);
      await page.setViewportSize(DESKTOP);
      await page.waitForTimeout(200);

      // --- 2. Customer chat from the storefront ---------------------------
      await expect(async () => {
        await page.getByRole("button", { name: chatButton }).click();
        await expect(page.getByRole("complementary", { name: chatButton })).toBeVisible();
      }).toPass({ timeout: 15_000 });
      const panel = page.getByRole("complementary", { name: chatButton });

      // The identity line is fixed; the configured greeting follows it.
      await expect(panel).toContainText(
        `Hi, I'm ${business.name}'s assistant. How can I help today?`,
      );
      await expect(panel).toContainText(business.greetingAdd);
      for (let i = 0; i < business.starters.length; i++) {
        await expect(page.getByTestId(`starter-${i}`)).toContainText(business.starters[i]);
      }
      await page.waitForTimeout(200);
      await shot(page, `03-${business.slug}-chat-start-desktop.png`);

      // A scripted turn: the live model is never on the path.
      await page.route("**/api/chat", (route) =>
        route.fulfill({
          status: 200,
          headers: { "content-type": "text/event-stream" },
          body: cardTurn(business),
        }),
      );
      await page.getByTestId("starter-0").click();

      const priceSummary = panel.getByLabel("Price summary");
      await expect(priceSummary).toBeVisible({ timeout: 15_000 });
      await expect(priceSummary).toContainText(business.card.itemLabel);
      // The amount is formatted from integer cents by the one money helper.
      await expect(priceSummary).toContainText(business.card.priceText);

      const catalog = panel.getByLabel("Catalog");
      await expect(catalog).toContainText(business.card.itemLabel);
      await expect(catalog).toContainText(business.card.priceText);
      await page.waitForTimeout(200);
      await shot(page, `04-${business.slug}-chat-reply-desktop.png`);

      // --- 3. Owner console queue -----------------------------------------
      const owner = DEMO_USERS.find((u) => u.email === business.ownerEmail)!;
      await loginAsTenantAdmin(page, request, owner);
      await page.goto("/chats");
      // Needs-you is the default; open All so businesses with no open
      // escalation still show their seeded threads.
      await page.getByTestId("chats-filter-all").click();
      await expect(page.getByTestId("chat-row").first()).toBeVisible({ timeout: 15_000 });

      const listText = await page.getByTestId("chats-list").innerText();
      for (const ref of business.ownRefs) {
        expect(listText).toContain(ref);
      }
      for (const ref of ALL_REFS.filter((r) => !business.ownRefs.includes(r))) {
        expect(listText).not.toContain(ref);
      }
      await shot(page, `05-${business.slug}-queue-desktop.png`);

      // --- 4. Console business hub ----------------------------------------
      await page.goto("/business");
      await expect(page.getByRole("navigation", { name: "Console" })).toContainText(business.name);
      await expect(page.getByRole("link", { name: /Business page/ })).toBeVisible();
      await page.waitForTimeout(200);
      await shot(page, `06-${business.slug}-business-hub-desktop.png`);
    });
  }

  /**
   * The surface proof of tenant isolation: each public page carries its own
   * unique offering and none of the other three, no owner email, and none of
   * the owner-only storefront controls. The data-layer isolation is pinned by
   * the backend leakage eval/tests; this is what a customer actually receives.
   */
  test("RF-17 cross-tenant isolation - each public page carries only its own business", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const ownerEmails = BUSINESSES.map((b) => b.ownerEmail);

    for (const business of BUSINESSES) {
      await page.setViewportSize(DESKTOP);
      await page.goto(`/${business.slug}`);
      await expect(async () => {
        await expect(page.getByRole("heading", { level: 1 })).toContainText(business.name);
        const main = page.getByRole("main");
        for (const other of BUSINESSES) {
          if (other.slug === business.slug) {
            await expect(main).toContainText(other.uniqueOffering);
          } else {
            await expect(main).not.toContainText(other.uniqueOffering);
          }
        }
        for (const email of ownerEmails) {
          await expect(main).not.toContainText(email);
        }
        await expect(page.getByTestId("owner-edit-name")).toHaveCount(0);
        await expect(page.getByTestId("owner-edit-fields")).toHaveCount(0);
      }).toPass({ timeout: 20_000 });
    }
  });
});
