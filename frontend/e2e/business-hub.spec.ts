/**
 * E2E for the Business hub and the screens under it (E-5 / D21 / M-1 / M-4).
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * The hub's shape is the thing under test as much as its contents: Stage 2
 * grows it by adding rows, so "exactly the rows that open onto something" is
 * the invariant worth pinning (PRD, "never build dead surfaces").
 */

import { test, expect } from "@playwright/test";
import {
  DEMO_USERS,
  loginAsTenantAdmin,
} from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;
const STAGE_2_ROWS = ["Schedule", "Money", "Plan"];

// A real, minimal 1x1 white JPEG. The cover path sends whatever the owner
// picks to the configured media store, and a non-image byte string is refused
// there - so this fixture has to be a decodable image whether the stack stores
// it in Cloudinary or in the legacy tenant_assets row.
const ONE_PX_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD2aiiigD//2Q==";

test.describe("Business hub", () => {

  test("holds only rows that open onto something", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");

    const rows = page.getByRole("main").getByRole("link");
    await expect(rows).toHaveText([
      "Business pageWhat customers see and how it looks",
      "What you offerThe services and prices shown on your page",
      "Business detailsKnowledge, ABN, and tax details",
    ]);

    // Absent, not disabled - the prototype carries them, Stage 1 does not.
    for (const label of STAGE_2_ROWS) {
      await expect(page.getByText(label, { exact: true })).toHaveCount(0);
    }
  });

  test("the business page shows the business and its public link", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");
    await page.getByRole("link", { name: /Business page/ }).click();
    await page.waitForURL("**/business/page");

    await expect(page.getByRole("heading", { level: 2 })).toContainText(
      "Bytefix",
    );

    // Derived from the current origin, so it is the address that actually
    // works from this browser - never a hardcoded domain.
    const link = page.getByTestId("booking-link");
    await expect(link).toContainText("/bytefix");
    await expect(link).not.toContainText("http");
    await expect(link).not.toContainText(/\/$/);

    const summary = page.getByRole("heading", { name: "What we offer" });
    await expect(summary).toBeVisible();
    await expect(page.getByText("iPhone 11 (Refurbished, 64GB)")).toBeVisible();
    await expect(page.getByText("$249.00")).toBeVisible();

    const sectionColors = await page
      .locator('[data-testid="offerings-summary"], [data-testid="booking-links"]')
      .evaluateAll((sections) =>
        sections.map((section) => getComputedStyle(section).backgroundColor),
      );
    expect(new Set(sectionColors).size).toBe(1);
  });

  test("an owner adds, edits, and removes an offering, and the storefront follows", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");
    await page.getByRole("link", { name: /What you offer/ }).click();
    await page.waitForURL("**/business/offerings");

    // These specs share one seeded tenant, so start from a known state rather
    // than from whatever a previous run left behind - the same posture the
    // link-slot test below takes. Gated on the loaded list: `count()` does
    // not retry, and counting before the first fetch lands would skip the
    // cleanup while a stale row is still on its way in.
    await expect(
      page.getByTestId("offerings-list").or(page.getByText("Nothing added yet.")),
    ).toBeVisible();
    const leftovers = page.getByRole("button", { name: "Remove M1 test offering" });
    while ((await leftovers.count()) > 0) {
      await leftovers.first().click();
      await page.getByTestId("confirm-accept").click();
      await expect(leftovers).toHaveCount(0);
    }

    await page.getByTestId("offering-add").click();
    await page.getByTestId("offering-name").fill("M1 test offering");
    await page.getByText("Add details", { exact: true }).click();
    await page.getByRole("textbox", { name: "Search categories" }).fill("Repairs");
    await page.getByRole("button", { name: "Repairs", exact: true }).click();
    await page.getByTestId("offering-description").fill("Most models");
    await page.getByTestId("offering-price").fill("89.50");
    await page.getByTestId("offering-media-mode-url").click();
    await page.getByTestId("offering-media-url").fill("https://youtu.be/example");
    await page.getByTestId("offering-save").click();
    await expect(page.getByTestId("offerings-list")).toContainText("M1 test offering");
    await expect(page.getByText("Offering added", { exact: true })).toBeVisible();

    // The price the owner typed, on the page a customer actually reads - and
    // exactly as typed. This is the assertion the money rule lives or dies by.
    // The offering is a row button, not a heading, on the catalogue layout.
    await page.goto("/bytefix");
    // `.first()`: `next dev` streams this page, so for a beat the server tree
    // and the client tree are both in the DOM - the same caveat
    // typing-indicator.spec.ts documents for the composer.
    await expect(
      page.getByRole("button", { name: /M1 test offering/ }).first(),
    ).toBeVisible();
    await expect(page.getByRole("main").last()).toContainText("$89.50");
    const card = page.getByRole("button", { name: /M1 test offering/ });
    await card.click();
    const details = page.getByRole("dialog", { name: "M1 test offering" });
    await expect(details.locator("iframe")).toHaveAttribute(
      "src",
      /youtube-nocookie\.com\/embed\//,
    );
    await details.getByRole("button", { name: "Ask about this" }).click();
    const chat = page.getByRole("dialog", { name: /Chat with Bytefix/ });
    await expect(chat.getByRole("textbox")).toHaveValue(
      "Tell me about M1 test offering",
    );

    await page.goto("/business/offerings");
    await page.getByRole("button", { name: "Edit M1 test offering" }).click();
    await page.getByTestId("offering-price").fill("99");
    await page.getByTestId("offering-save").click();
    await expect(page.getByTestId("offerings-list")).toContainText("$99.00");
    await expect(page.getByText("Offering saved", { exact: true })).toBeVisible();

    await page.goto("/bytefix");
    await expect(page.getByRole("main").last()).toContainText("$99.00");

    await page.goto("/business/offerings");
    await page.getByRole("button", { name: "Remove M1 test offering" }).click();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByTestId("offerings-list")).not.toContainText("M1 test offering");
    await expect(page.getByText("Offering removed", { exact: true })).toBeVisible();

    // Retiring it takes it off the storefront too, not just out of the editor.
    await page.goto("/bytefix");
    await expect(page.getByRole("main").last()).not.toContainText("M1 test offering");
  });

  test("an owner manages multi-category membership and primary promotion", async ({
    page,
    request,
  }) => {
    const offeringName = "Category journey offering";
    const originalFirstCategory = "E2E Device care";
    const firstCategory = "E2E Device support";
    const secondCategory = "E2E Featured repairs";
    const cancelledCategory = "E2E Cancelled category";

    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/offerings");
    await expect(
      page.getByTestId("offerings-list").or(page.getByText("Nothing added yet.")),
    ).toBeVisible();

    const staleOffering = page.getByRole("button", { name: `Remove ${offeringName}` });
    while ((await staleOffering.count()) > 0) {
      await staleOffering.first().click();
      await page.getByTestId("confirm-accept").click();
      await expect(staleOffering).toHaveCount(0);
    }
    for (const categoryName of [originalFirstCategory, firstCategory, secondCategory]) {
      const staleCategory = page.getByRole("button", { name: `Remove ${categoryName}` });
      if (await staleCategory.count()) {
        await staleCategory.click();
        await page.getByTestId("confirm-accept").click();
        await expect(staleCategory).toHaveCount(0);
      }
    }

    const categorySection = page.getByRole("region", { name: "Categories" });
    await categorySection.getByTestId("category-add").click();
    const newCategoryDialog = page.getByRole("dialog", { name: "New category" });
    await newCategoryDialog.getByTestId("category-name").fill(cancelledCategory);
    await newCategoryDialog.getByRole("button", { name: "Cancel" }).click();
    await expect(newCategoryDialog).not.toBeVisible();
    await expect(page.getByTestId("categories-list")).not.toContainText(cancelledCategory);

    for (const categoryName of [originalFirstCategory, secondCategory]) {
      await categorySection.getByTestId("category-add").click();
      await newCategoryDialog.getByTestId("category-name").fill(categoryName);
      await newCategoryDialog.getByTestId("category-save").click();
      await expect(page.getByTestId("categories-list")).toContainText(categoryName);
    }

    await page.getByRole("button", { name: `Edit ${originalFirstCategory}` }).click();
    const editCategoryDialog = page.getByRole("dialog", { name: "Edit category" });
    await expect(editCategoryDialog.getByTestId("category-name")).toHaveValue(
      originalFirstCategory,
    );
    await editCategoryDialog.getByTestId("category-name").fill(firstCategory);
    await editCategoryDialog.getByTestId("category-save").click();
    await expect(page.getByText("Category renamed", { exact: true })).toBeVisible();
    await expect(page.getByTestId("categories-list")).toContainText(firstCategory);
    await expect(page.getByTestId("categories-list")).not.toContainText(originalFirstCategory);

    await page.getByTestId("offering-add").click();
    await page.getByTestId("offering-name").fill(offeringName);
    await page.getByText("Add details", { exact: true }).click();
    const categorySearch = page.getByRole("textbox", { name: "Search categories" });
    for (const categoryName of [firstCategory, secondCategory]) {
      await categorySearch.fill(categoryName);
      await page.getByRole("button", { name: categoryName, exact: true }).click();
    }
    await page.getByRole("button", { name: `Make ${secondCategory} primary` }).click();
    await page.getByTestId("offering-save").click();
    await expect(page.getByText("Offering added", { exact: true })).toBeVisible();
    await expect(page.getByTestId("offerings-list")).toContainText(firstCategory);
    await expect(
      page.getByTestId("offerings-list").getByRole("heading", {
        name: secondCategory,
        exact: true,
      }),
    ).toBeVisible();

    await page.goto("/bytefix");
    await expect(
      page.getByRole("heading", { name: firstCategory, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: secondCategory, exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: offeringName, exact: true })).toHaveCount(2);

    await page.goto("/business/offerings");
    await page.getByRole("button", { name: `Remove ${secondCategory}` }).click();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByText("Category removed", { exact: true })).toBeVisible();
    await expect(
      page.getByTestId("offerings-list").getByRole("heading", {
        name: firstCategory,
        exact: true,
      }),
    ).toBeVisible();

    await page.goto("/bytefix");
    await expect(page.getByRole("heading", { name: secondCategory, exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: offeringName, exact: true })).toHaveCount(1);

    await page.goto("/business/offerings");
    await page.getByRole("button", { name: `Remove ${offeringName}` }).click();
    await page.getByTestId("confirm-accept").click();
    await page.getByRole("button", { name: `Remove ${firstCategory}` }).click();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByRole("button", { name: `Remove ${firstCategory}` })).toHaveCount(0);
  });

  test("escape closes the remove confirm without touching the backend", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/offerings");

    await page.getByTestId("offering-add").click();
    await page.getByTestId("offering-name").fill("M1 cancel-remove probe");
    await page.getByTestId("offering-save").click();
    await expect(page.getByTestId("offerings-list")).toContainText("M1 cancel-remove probe");

    let deletes = 0;
    await page.route("**/api/business/offerings/*", (route) => {
      if (route.request().method() === "DELETE") deletes += 1;
      return route.continue();
    });

    await page.getByRole("button", { name: "Remove M1 cancel-remove probe" }).click();
    await expect(page.getByTestId("confirm-accept")).toBeVisible();
    await page.keyboard.press("Escape");
    // A closed confirm renders nothing, so "closed" means no accept button
    // in the tree - never a visibility assertion on the dialog role.
    await expect(page.getByTestId("confirm-accept")).toHaveCount(0);
    expect(deletes).toBe(0);
    await expect(page.getByTestId("offerings-list")).toContainText("M1 cancel-remove probe");

    // Clean up through the real confirm path.
    await page.getByRole("button", { name: "Remove M1 cancel-remove probe" }).click();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByTestId("offerings-list")).not.toContainText("M1 cancel-remove probe");
  });

  test("uploading media shows a preview with Edit and Cancel, and Cancel sends nothing", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/offerings");

    await expect(
      page.getByTestId("offerings-list").or(page.getByText("Nothing added yet.")),
    ).toBeVisible();
    const probeLeftovers = page.getByRole("button", { name: "Remove M1 media-button probe" });
    while ((await probeLeftovers.count()) > 0) {
      await probeLeftovers.first().click();
      await page.getByTestId("confirm-accept").click();
      await expect(probeLeftovers).toHaveCount(0);
    }

    await page.getByTestId("offering-add").click();
    await page.getByTestId("offering-name").fill("M1 media-button probe");
    await page.getByText("Add details", { exact: true }).click();

    // Upload reads as a button, not native file text.
    const upload = page.getByTestId("offering-media-upload");
    await expect(upload).toBeVisible();
    await expect(upload).toHaveAttribute("aria-label", "Upload media");

    let mediaCalls = 0;
    await page.route("**/api/business/offerings/*/media**", (route) => {
      mediaCalls += 1;
      return route.continue();
    });

    await page.getByTestId("offering-media-input").setInputFiles({
      name: "probe.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from("probe-image-bytes"),
    });
    await expect(page.getByTestId("offering-media-preview")).toBeVisible();
    await expect(page.getByTestId("offering-media-filename")).toContainText("probe.jpg");
    await expect(page.getByTestId("offering-media-edit")).toBeVisible();
    await expect(page.getByTestId("offering-media-cancel")).toBeVisible();

    // Cancel drops the pending pick locally - no media traffic at all.
    await page.getByTestId("offering-media-cancel").click();
    await expect(page.getByTestId("offering-media-preview")).toHaveCount(0);
    await expect(upload).toBeVisible();
    expect(mediaCalls).toBe(0);

    // Saving after a cancel performs no media call either.
    await page.getByTestId("offering-save").click();
    await expect(page.getByTestId("offerings-list")).toContainText("M1 media-button probe");
    expect(mediaCalls).toBe(0);

    // Clean up through the real remove path.
    await page.getByRole("button", { name: "Remove M1 media-button probe" }).click();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByTestId("offerings-list")).not.toContainText("M1 media-button probe");
  });

  test("an owner replaces and removes an offering's media by URL", async ({
    page,
    request,
  }) => {
    const offeringName = "RF-5 media URL probe";
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/offerings");

    await expect(
      page.getByTestId("offerings-list").or(page.getByText("Nothing added yet.")),
    ).toBeVisible();
    const leftovers = page.getByRole("button", { name: `Remove ${offeringName}` });
    while ((await leftovers.count()) > 0) {
      await leftovers.first().click();
      await page.getByTestId("confirm-accept").click();
      await expect(leftovers).toHaveCount(0);
    }

    await page.getByTestId("offering-add").click();
    await page.getByTestId("offering-name").fill(offeringName);
    await page.getByText("Add details", { exact: true }).click();
    await page.getByTestId("offering-media-mode-url").click();
    await page.getByTestId("offering-media-url").fill("https://youtu.be/first");
    await page.getByTestId("offering-save").click();
    await expect(page.getByText("Offering added", { exact: true })).toBeVisible();

    // Reopen: the saved URL reads back and the explicit remove is offered.
    await page.getByRole("button", { name: `Edit ${offeringName}` }).click();
    const sheet = page.getByRole("dialog", { name: "Edit offering" });
    await expect(page.getByTestId("offering-media-url")).toHaveValue(
      "https://youtu.be/first",
    );
    await expect(page.getByTestId("offering-media-remove")).toBeVisible();

    // Replace it with another URL.
    await page.getByTestId("offering-media-url").fill("https://vimeo.com/second");
    await page.getByTestId("offering-save").click();
    await expect(page.getByText("Offering saved", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: `Edit ${offeringName}` }).click();
    await expect(page.getByTestId("offering-media-url")).toHaveValue(
      "https://vimeo.com/second",
    );

    // Removal is explicit and confirmed through the shared dialog, then saved.
    await page.getByTestId("offering-media-remove").click();
    await expect(
      page.getByRole("dialog", { name: "Remove this photo?" }),
    ).toBeVisible();
    await page.getByTestId("confirm-accept").click();
    await expect(
      page.getByText("Current media will be removed when you save."),
    ).toBeVisible();
    await page.getByTestId("offering-save").click();
    await expect(page.getByText("Offering saved", { exact: true }).last()).toBeVisible();

    // Reopen: empty media starts on Upload, with no URL field or remove link.
    // With nothing left on the offering the details block is collapsed.
    await page.getByRole("button", { name: `Edit ${offeringName}` }).click();
    await page.getByText("Add details", { exact: true }).click();
    await expect(page.getByTestId("offering-media-url")).toHaveCount(0);
    await expect(page.getByTestId("offering-media-upload")).toBeVisible();
    await expect(page.getByTestId("offering-media-remove")).toHaveCount(0);
    await sheet.getByRole("button", { name: "Cancel" }).click();

    // Clean up through the real remove path.
    await page.getByRole("button", { name: `Remove ${offeringName}` }).click();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByTestId("offerings-list")).not.toContainText(offeringName);
  });

  test("switching a pending pick to URL drops it and restores the saved link", async ({
    page,
    request,
  }) => {
    const offeringName = "RF-5 media toggle probe";
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/offerings");

    await expect(
      page.getByTestId("offerings-list").or(page.getByText("Nothing added yet.")),
    ).toBeVisible();
    const leftovers = page.getByRole("button", { name: `Remove ${offeringName}` });
    while ((await leftovers.count()) > 0) {
      await leftovers.first().click();
      await page.getByTestId("confirm-accept").click();
      await expect(leftovers).toHaveCount(0);
    }

    await page.getByTestId("offering-add").click();
    await page.getByTestId("offering-name").fill(offeringName);
    await page.getByText("Add details", { exact: true }).click();
    await page.getByTestId("offering-media-mode-url").click();
    await page.getByTestId("offering-media-url").fill("https://youtu.be/keep");
    await page.getByTestId("offering-save").click();
    await expect(page.getByText("Offering added", { exact: true })).toBeVisible();

    // Reopen on the saved URL, stage a file, then leave the upload side: the
    // pending pick drops and the saved link comes back.
    await page.getByRole("button", { name: `Edit ${offeringName}` }).click();
    await expect(page.getByTestId("offering-media-url")).toHaveValue("https://youtu.be/keep");
    await page.getByTestId("offering-media-mode-upload").click();
    await page.getByTestId("offering-media-input").setInputFiles({
      name: "toggle.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from("toggle-image-bytes"),
    });
    await expect(page.getByTestId("offering-media-preview")).toBeVisible();

    await page.getByTestId("offering-media-mode-url").click();
    await expect(page.getByTestId("offering-media-preview")).toHaveCount(0);
    await expect(page.getByTestId("offering-media-url")).toHaveValue("https://youtu.be/keep");

    // Cancel sends nothing; clean up through the real remove path.
    await page.getByRole("dialog", { name: "Edit offering" }).getByRole("button", { name: "Cancel" }).click();
    await page.getByRole("button", { name: `Remove ${offeringName}` }).click();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByTestId("offerings-list")).not.toContainText(offeringName);
  });

  test("saving a picked offering image uploads through the shared field", async ({
    page,
    request,
  }) => {
    const offeringName = "RF-5 media upload probe";
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/offerings");

    await expect(
      page.getByTestId("offerings-list").or(page.getByText("Nothing added yet.")),
    ).toBeVisible();
    const leftovers = page.getByRole("button", { name: `Remove ${offeringName}` });
    while ((await leftovers.count()) > 0) {
      await leftovers.first().click();
      await page.getByTestId("confirm-accept").click();
      await expect(leftovers).toHaveCount(0);
    }

    // The local stack has no Cloudinary, so only the upload PUT is mocked. The
    // pick, the preview and the save are the real shared field and the real
    // backend; nothing reaches Cloudinary.
    let uploads = 0;
    await page.route("**/api/business/offerings/*/media/upload", async (route) => {
      uploads += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          url: "https://example.test/probe.jpg",
          type: "image",
          provider: "cloudinary",
        }),
      });
    });

    await page.getByTestId("offering-add").click();
    await page.getByTestId("offering-name").fill(offeringName);
    await page.getByText("Add details", { exact: true }).click();
    await page.getByTestId("offering-media-input").setInputFiles({
      name: "probe.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from("probe-image-bytes"),
    });
    await expect(page.getByTestId("offering-media-preview")).toBeVisible();
    await expect(page.getByTestId("offering-media-filename")).toContainText("probe.jpg");
    await expect(page.getByTestId("offering-media-edit")).toBeVisible();
    await expect(page.getByTestId("offering-media-cancel")).toBeVisible();

    await page.getByTestId("offering-save").click();
    await expect(page.getByText("Offering added", { exact: true })).toBeVisible();
    expect(uploads).toBe(1);

    // Clean up through the real remove path.
    await page.getByRole("button", { name: `Remove ${offeringName}` }).click();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByTestId("offerings-list")).not.toContainText(offeringName);
  });

  test("copying puts the full URL, scheme and all, on the clipboard", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");

    await page.getByTestId("booking-copy").click();
    await expect(page.getByTestId("booking-copy")).toContainText("Copied");

    const copied = await page.evaluate(() => navigator.clipboard.readText());
    // The pill hides the scheme; what a customer needs is the whole thing.
    expect(copied).toMatch(/^https?:\/\/[^/]+\/bytefix$/);
  });

  test("the cover photo and the link slots", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");

    // E-6: the QR went. It was never in the prototype's owner screen, and the
    // founder does not use it. Pinned so it does not drift back in.
    await expect(page.getByTestId("booking-qr")).toHaveCount(0);
    // Nor is there a "Get a quote" CTA: quoting is a Stage 2 opt-in.
    await expect(page.getByRole("button", { name: "Get a quote" })).toHaveCount(
      0,
    );

    // The cover well invites a photo before there is one.
    await expect(page.getByTestId("booking-cover")).toBeVisible();
    await expect(page.getByTestId("booking-cover")).toContainText(
      "cover photo",
    );

    // Four slots, each either offering to take a link or offering to open one.
    // Not asserted as "all empty": these specs share one seeded tenant, so a
    // slot's contents are another test's business, not this one's.
    for (const key of ["website", "google", "facebook", "instagram"]) {
      await expect(page.getByTestId(`booking-platform-${key}`)).toContainText(
        /Add|Open/,
      );
    }
  });

  test("an owner uploads, replaces, and removes the cover photo", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");
    // Wait for the page payload: the cover control's remove affordance only
    // appears once has_cover is known, so checking it any earlier is a race.
    await expect(page.getByTestId("booking-link")).toBeVisible();

    // Shared tenant: clear anything a previous run left, so this starts empty.
    if (await page.getByTestId("booking-cover-remove").isVisible()) {
      await page.getByTestId("booking-cover-remove").click();
      await page.getByTestId("confirm-accept").click();
      await expect(page.getByTestId("booking-cover-remove")).toHaveCount(0);
    }
    await expect(page.getByTestId("booking-cover")).toContainText("cover photo");

    // Upload: the well takes a real JPEG, downscale re-encodes it client-side,
    // and the configured media store keeps it - Cloudinary when configured,
    // the legacy tenant_assets row otherwise. The explicit remove appears.
    await page.getByTestId("booking-cover-input").setInputFiles({
      name: "cover-a.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from(ONE_PX_JPEG_BASE64, "base64"),
    });
    await expect(page.getByText("Cover photo updated", { exact: true }).last()).toBeVisible();
    await expect(page.getByTestId("booking-cover-remove")).toBeVisible();

    // Replace: a second file lands and the cover is still saved and removable.
    await page.getByTestId("booking-cover-input").setInputFiles({
      name: "cover-b.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from(ONE_PX_JPEG_BASE64, "base64"),
    });
    await expect(page.getByText("Cover photo updated", { exact: true }).last()).toBeVisible();
    await expect(page.getByTestId("booking-cover-remove")).toBeVisible();

    // Removal is explicit and confirmed, and lands back on the empty well.
    await page.getByTestId("booking-cover-remove").click();
    await expect(
      page.getByRole("dialog", { name: "Remove cover photo?" }),
    ).toBeVisible();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByText("Cover photo removed", { exact: true })).toBeVisible();
    await expect(page.getByTestId("booking-cover-remove")).toHaveCount(0);
    await expect(page.getByTestId("booking-cover")).toContainText("cover photo");
  });

  test("a failed cover upload restores the previous photo", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");
    await expect(page.getByTestId("booking-link")).toBeVisible();

    if (await page.getByTestId("booking-cover-remove").isVisible()) {
      await page.getByTestId("booking-cover-remove").click();
      await page.getByTestId("confirm-accept").click();
      await expect(page.getByTestId("booking-cover-remove")).toHaveCount(0);
    }

    await page.getByTestId("booking-cover-input").setInputFiles({
      name: "cover-first.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from(ONE_PX_JPEG_BASE64, "base64"),
    });
    await expect(page.getByText("Cover photo updated", { exact: true })).toBeVisible();
    await expect(page.getByTestId("booking-cover-remove")).toBeVisible();

    // Fail only the next PUT; GET keeps working so the old cover can return.
    await page.route("**/api/business/cover", async (route) => {
      if (route.request().method() === "PUT") {
        await route.fulfill({
          status: 502,
          contentType: "application/json",
          body: JSON.stringify({
            type: "about:blank",
            detail: "the cover could not be stored",
            code: "media_upload_failed",
          }),
        });
        return;
      }
      await route.continue();
    });

    await page.getByTestId("booking-cover-input").setInputFiles({
      name: "cover-fail.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from(ONE_PX_JPEG_BASE64, "base64"),
    });
    await expect(
      page.getByText("That image could not be saved. Try a JPEG or PNG under 2MB."),
    ).toBeVisible();
    // The failed pick left no partial state: the previous cover is still
    // rendered and still removable.
    await expect(page.getByTestId("booking-cover-remove")).toBeVisible();
    await expect(page.getByTestId("booking-cover").locator("img")).toBeVisible();

    // Clean up through the real remove path.
    await page.unroute("**/api/business/cover");
    await page.getByTestId("booking-cover-remove").click();
    await page.getByTestId("confirm-accept").click();
    await expect(page.getByTestId("booking-cover-remove")).toHaveCount(0);
  });

  test("a link slot takes an address, keeps it, and then opens it", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");

    const tile = page.getByTestId("booking-platform-instagram");

    // These specs share one seeded tenant, so start from a known slot rather
    // than from whatever a previous run left behind.
    await tile.click();
    if (await page.getByTestId("booking-link-remove").isVisible()) {
      await page.getByTestId("booking-link-remove").click();
      await page.getByTestId("confirm-accept").click();
      await expect(tile).toContainText("Add");
      await tile.click();
    }

    // Pasted without a scheme, the way an address bar shows it.
    await page.getByTestId("booking-link-input").fill("instagram.com/bytefix");
    await page.getByTestId("booking-link-save").click();
    await expect(tile).toContainText("Open");
    await expect(page.getByText("Link saved", { exact: true })).toBeVisible();

    // It survives a reload - this is the assertion that catches a save that
    // only ever updated local state.
    await page.reload();
    await expect(tile).toContainText("Open");

    // And it is a way out to that page, with the scheme filled in. Asserted on
    // the href rather than by following it: a real popup would assert on
    // whatever instagram.com redirects to that day, which is a test of their
    // infrastructure, not ours.
    await tile.click();
    await expect(page.getByTestId("booking-link-open")).toHaveAttribute(
      "href",
      "https://instagram.com/bytefix",
    );

    // Put the slot back, so this spec leaves the shared tenant as it found it.
    await page.getByTestId("booking-link-remove").click();
    await page.getByTestId("confirm-accept").click();
    await expect(tile).toContainText("Add");
    await expect(page.getByText("Link removed", { exact: true })).toBeVisible();
  });

  test("back from the business page returns to the hub", async ({
    page,
    request,
  }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/page");
    await page.getByRole("button", { name: "Back" }).click();
    await page.waitForURL("**/business");
  });
});
