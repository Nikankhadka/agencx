/**
 * E2E for ticket 26: owner actions on the Business page.
 *
 * Surface: tenant-admin (http://localhost:3000/business/page)
 *
 * Both tests mock the page/profile (and suggestions) endpoints so the run does
 * not depend on the seeded world's catalog state. The login is real, so the
 * session and the page shell still come from the running stack.
 */

import { test, expect } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

// The full BusinessProfile shape the sheet reads (name, hours, description,
// business_contact, abn, gst, services, customer_voice_preset,
// customer_voice_custom_style).
const PROFILE = {
  name: "Bytefix Repairs",
  hours: "",
  description: "",
  business_contact: "",
  abn: "",
  gst: "",
  services: ["Phone repair"],
  customer_voice_preset: "warm_casual",
  customer_voice_custom_style: "",
};

test.describe("Business page actions", () => {
  test("editing services from the empty overview saves and refetches the page", async ({
    page,
    request,
  }) => {
    // Mutable state behind the mocks, so the refetch after Save reads back the
    // services the PATCH just stored.
    let pageData = {
      slug: "bytefix",
      name: "Bytefix Repairs",
      tagline: "",
      description: "",
      business_contact: "",
      has_cover: false,
      services: ["Phone repair"],
      offerings: [] as { id: string }[],
      links: {} as Record<string, string>,
    };
    let profileData = { ...PROFILE };
    let pageGets = 0;
    const patches: { services?: string[] }[] = [];

    // Query-string-safe globs. Registered first so nothing broader can shadow
    // the suggestions stub.
    await page.route("**/api/onboarding/suggestions*", (route) =>
      route.fulfill({ json: { count: 0, candidates: [] } }),
    );
    await page.route("**/api/business/page*", (route) => {
      pageGets += 1;
      return route.fulfill({ json: pageData });
    });
    await page.route("**/api/business/profile*", (route) => {
      if (route.request().method() === "PATCH") {
        const body = JSON.parse(route.request().postData() ?? "{}") as {
          services?: string[];
        };
        patches.push(body);
        profileData = { ...profileData, ...body };
        pageData = { ...pageData, services: profileData.services };
        return route.fulfill({ json: profileData });
      }
      return route.fulfill({ json: profileData });
    });

    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");

    // Empty catalog: the owner's own overview, with the owner-only Edit.
    await expect(page.getByTestId("services-overview")).toBeVisible();
    await expect(page.getByTestId("services-overview-edit")).toBeVisible();

    await page.getByTestId("services-overview-edit").click();

    // The Sheet is always mounted (toggling inert), so "open" is the inert
    // wrapper disappearing around the sheet body, not a visibility assertion.
    // CSS locators inside `has` (not role/label) because inert hides the
    // subtree from the accessibility tree.
    const serviceInput = page.getByLabel("Service 1", { exact: true });
    const closedSheet = page
      .locator("div[inert]")
      .filter({ has: page.locator('input[aria-label="Service 1"]') });
    await expect(closedSheet).toHaveCount(0);
    await expect(serviceInput).toBeVisible();
    await serviceInput.fill("Phone and laptop repair");

    const before = pageGets;
    await page.getByTestId("services-save").click();

    await expect.poll(() => patches.length).toBeGreaterThan(0);
    expect(patches.at(-1)?.services).toEqual(["Phone and laptop repair"]);
    await expect.poll(() => pageGets).toBeGreaterThan(before);
    await expect(page.getByTestId("services-overview")).toContainText(
      "Phone and laptop repair",
    );
  });

  test("pending candidates are reviewable from the Business page", async ({
    page,
    request,
  }) => {
    const candidates = [
      {
        candidate_id: "c1",
        name: "Battery swap",
        description: "",
        price_cents: null,
        sources: ["document"],
        review_status: "pending",
      },
      {
        candidate_id: "c2",
        name: "Screen repair",
        description: "",
        price_cents: null,
        sources: ["document"],
        review_status: "pending",
      },
    ];

    await page.route("**/api/onboarding/suggestions*", (route) =>
      route.fulfill({ json: { count: candidates.length, candidates } }),
    );
    // Non-empty catalog: the offerings summary renders, not the overview, and
    // the card must still show.
    await page.route("**/api/business/page*", (route) =>
      route.fulfill({
        json: {
          slug: "bytefix",
          name: "Bytefix Repairs",
          tagline: "",
          description: "",
          business_contact: "",
          has_cover: false,
          services: [],
          offerings: [
            {
              id: "o1",
              name: "iPhone 11",
              description: "",
              price_cents: 24900,
              category: null,
              media: null,
            },
          ],
          links: {},
        },
      }),
    );

    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");

    await expect(
      page.getByText("2 offerings waiting for review"),
    ).toBeVisible();
    // Always mounted: the sheet starts inert and the click clears it. Text
    // match, not a role query, because inert hides the subtree from the
    // accessibility tree.
    const closedSuggestions = page
      .locator("div[inert]")
      .filter({ hasText: "Suggestions to review" });
    await expect(closedSuggestions).toHaveCount(1);
    await page.getByRole("button", { name: "Review suggestions" }).click();
    await expect(closedSuggestions).toHaveCount(0);

    await expect(
      page.getByRole("heading", { name: "Suggestions to review" }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "These private drafts never reach customers until you save them.",
      ),
    ).toBeVisible();
  });
});
