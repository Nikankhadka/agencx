import { expect, test, type Locator, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";
import {
  MIDDLE_DOT,
  draftRecord,
  offeringCandidate,
  onboardingState,
  recordsStore,
  stubBatch,
  stubOnboardingState,
  stubRecords,
  stubSourceUrl,
  stubUpload,
  uploadFilePayloads,
} from "./knowledge-review-mocks";

/**
 * W-11c: the combined document review on desktop - bounded-concurrency batch
 * upload, the five-file cap, stored failures, the ready card with W-11b edit
 * retention, safe replace, offering reconciliation, batch publish with a
 * partial failure, and pagination/toolbar behavior.
 *
 * Fully mocked, following the pattern in onboarding-transport.spec.ts:
 * page.route on `/api/onboarding/state` and `/api/knowledge/records` (the
 * page's mount does Promise.all over both), installed before
 * loginAsTenantAdmin. Upload, batch and DELETE routes are stateful stubs the
 * tests assert against.
 */

const FIVE_NAMES = ["menu.txt", "hours.txt", "policies.txt", "notes.txt", "faq.txt"];
const SEVEN_NAMES = [...FIVE_NAMES, "extra6.txt", "extra7.txt"];

function dialog(page: Page) {
  return page.getByRole("dialog", { name: "Review your information" });
}

/** 31: a revealed field must actually be on screen, not just focused. */
async function expectInViewport(locator: Locator) {
  const box = await locator.boundingBox();
  const viewport = locator.page().viewportSize()!;
  expect(box).not.toBeNull();
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height);
}

test("uploads five files three at a time and opens one combined review", async ({
  page,
  request,
}) => {
  const store = recordsStore([]);
  // 29: the "+" is on every text stage, so this exercises the plain drafts
  // batch from an ordinary beat - the source stage has its own endpoint.
  await stubOnboardingState(page);
  await stubRecords(page, store);
  let nextId = 1;
  const upload = await stubUpload(page, store, {
    delayMs: 300,
    recordFor: (filename) =>
      draftRecord({ id: `draft-${nextId++}`, filename, sections: [{ heading: "Hours", body: "9 to 5" }] }),
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  const thread = page.getByTestId("onboarding-thread");
  await expect(thread).toBeVisible();

  await page.getByTestId("onboarding-file-input").setInputFiles(uploadFilePayloads(FIVE_NAMES));

  // Mid-flight: the review sheet has not opened - it opens only once every
  // upload has settled, never on the first accepted draft.
  await expect(dialog(page)).toHaveCount(0);

  await expect.poll(() => upload.settled()).toBe(5);
  // runBounded(5, 3): never more than three in flight, and all three of the
  // first wave really do run together.
  expect(upload.maxInFlight()).toBeLessThanOrEqual(3);
  expect(upload.maxInFlight()).toBeGreaterThanOrEqual(2);

  for (const name of FIVE_NAMES) {
    await expect(
      thread.getByText(`${name} ${MIDDLE_DOT} ready`, { exact: true }),
    ).toBeVisible();
  }
  await expect(thread.getByText("I can take up to 5 files at once...")).toHaveCount(0);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  for (const name of FIVE_NAMES) {
    await expect(sheet.getByText(name, { exact: true })).toBeVisible();
  }
});

test("caps the batch at five files", async ({ page, request }) => {
  const store = recordsStore([]);
  await stubOnboardingState(page);
  await stubRecords(page, store);
  let nextId = 1;
  const upload = await stubUpload(page, store, {
    delayMs: 200,
    recordFor: (filename) => draftRecord({ id: `draft-${nextId++}`, filename }),
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  const thread = page.getByTestId("onboarding-thread");
  await expect(thread).toBeVisible();

  await page.getByTestId("onboarding-file-input").setInputFiles(uploadFilePayloads(SEVEN_NAMES));

  // The sixth and seventh files are turned away in one line; only the first
  // five are processed and stamped.
  await expect(thread.getByText("I can take up to 5 files at once...")).toBeVisible();
  await expect.poll(() => upload.settled()).toBe(5);
  await expect(thread.getByText(new RegExp(`${MIDDLE_DOT} ready$`))).toHaveCount(5);
  await expect(thread.getByText("extra6.txt · ready", { exact: true })).toHaveCount(0);
  await expect(thread.getByText("extra7.txt · ready", { exact: true })).toHaveCount(0);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  for (const name of FIVE_NAMES) {
    await expect(sheet.getByText(name, { exact: true })).toBeVisible();
  }
  await expect(sheet.getByText("extra6.txt", { exact: true })).toHaveCount(0);
});

test("a stored failure stays in Knowledge and never joins the review", async ({
  page,
  request,
}) => {
  const store = recordsStore([]);
  await stubOnboardingState(page);
  const records = await stubRecords(page, store);
  await stubUpload(page, store, {
    recordFor: (filename) =>
      draftRecord({
        id: "draft-failed-1",
        filename,
        status: "failed",
        error: "Extraction failed",
        failure_stage: "extract",
        failure_retryable: true,
        failed_at: "2026-09-11T00:00:00Z",
      }),
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  const thread = page.getByTestId("onboarding-thread");
  await expect(thread).toBeVisible();

  await page
    .getByTestId("onboarding-file-input")
    .setInputFiles(uploadFilePayloads(["menu.txt"]));

  await expect(thread.getByText("menu.txt · failed", { exact: true })).toBeVisible();
  await expect(thread.getByText("It's kept in Knowledge so you can retry it.")).toBeVisible();
  // Not a reviewable draft: no sheet, no ready card.
  await expect(dialog(page)).toHaveCount(0);
  await expect(page.getByTestId("onboarding-ready-card")).toHaveCount(0);

  // The failed row lives in the records list the page loads - a reload
  // refetches it (the GET happened and returned it) and still shows nothing
  // reviewable.
  await page.reload();
  await expect(thread).toBeVisible();
  expect(records.getCount()).toBeGreaterThanOrEqual(2);
  expect(JSON.parse(records.lastGetBody())).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: "draft-failed-1",
        status: "failed",
        failure_retryable: true,
      }),
    ]),
  );
  await expect(dialog(page)).toHaveCount(0);
  await expect(page.getByTestId("onboarding-ready-card")).toHaveCount(0);
});

test("the ready card persists and reopens with edits intact", async ({ page, request }) => {
  const store = recordsStore([draftRecord()]);
  await stubOnboardingState(page);
  await stubRecords(page, store);

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  // One offering: collapsed, so no Review all in the toolbar.
  await expect(sheet.getByRole("button", { name: /Review all/ })).toHaveCount(0);

  // The sheet's own focus effect must land before Escape can reach its
  // keydown handler - the key goes to whatever has focus.
  await expect(sheet.getByRole("button", { name: "Close" })).toBeFocused();
  await page.keyboard.press("Escape");
  const card = page.getByTestId("onboarding-ready-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("Documents ready to review")).toBeVisible();
  await expect(card.getByText("1 source is read and waiting")).toBeVisible();

  await page.getByTestId("onboarding-reopen-review").click();
  await expect(sheet).toBeVisible();
  // The sheet's own focus effect must land before Escape can reach its
  // keydown handler - the key goes to whatever has focus.
  await expect(sheet.getByRole("button", { name: "Close" })).toBeFocused();

  // 29: the structured sections sit behind "More about what I read", closed
  // by default. Open the disclosure, then the section's own editor.
  await sheet.getByTestId("review-more-about-source").click();
  await sheet
    .getByRole("heading", { name: "Hours", exact: true })
    .locator("..")
    .getByRole("button", { name: "Edit" })
    .click();
  const edited = "9 to 5, Monday to Friday, closed Sundays";
  const details = sheet.getByLabel("Hours details");
  await details.fill(edited);
  await expect(details).toHaveValue(edited);

  // Close via Escape - not discard - so the workspace survives, then come
  // back through the card: the edit is still there (W-11b retention).
  await page.keyboard.press("Escape");
  await expect(card).toBeVisible();
  await page.getByTestId("onboarding-reopen-review").click();
  await expect(sheet).toBeVisible();
  await expect(sheet.getByLabel("Hours details")).toHaveValue(edited);
});

test("replace is safe when the upload fails", async ({ page, request }) => {
  const store = recordsStore([
    draftRecord({
      id: "draft-1",
      filename: "menu.txt",
      offering_candidates: [offeringCandidate("Menu item A", "draft-1")],
    }),
  ]);
  await stubOnboardingState(page);
  const records = await stubRecords(page, store);
  await stubUpload(page, store, {
    failAll: true,
    recordFor: () => draftRecord({ id: "draft-new", filename: "new.txt" }),
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  await expect(sheet.getByText("menu.txt", { exact: true })).toBeVisible();
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("Menu item A");

  await sheet.getByRole("button", { name: "Replace menu.txt" }).click();
  await sheet.getByTestId("review-replace-input").setInputFiles({
    name: "new.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("New contents"),
  });

  // Upload failed, so the DELETE never fired and the old source and its
  // offerings are untouched.
  await expect(
    page.getByTestId("onboarding-thread").getByText("new.txt · failed", { exact: true }),
  ).toBeVisible();
  expect(records.deleteCount()).toBe(0);
  await expect(sheet.getByText("menu.txt", { exact: true })).toBeVisible();
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("Menu item A");
});

test("a successful replace reconciles offering provenance", async ({ page, request }) => {
  const store = recordsStore([
    draftRecord({
      id: "draft-1",
      filename: "menu.txt",
      offering_candidates: [offeringCandidate("Menu item A", "draft-1")],
    }),
    draftRecord({
      id: "draft-2",
      filename: "notes.txt",
      offering_candidates: [offeringCandidate("Menu item B", "draft-2")],
    }),
  ]);
  await stubOnboardingState(page);
  const records = await stubRecords(page, store);
  await stubUpload(page, store, {
    recordFor: (filename) =>
      draftRecord({
        id: "draft-3",
        filename,
        offering_candidates: [offeringCandidate("Menu item C", "draft-3")],
      }),
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  // Labels live on the offering cards (articles) - the Business information
  // section repeats the "From {label}" line for multi-document reviews.
  const cards = sheet.locator("article");
  await expect(cards.getByText("From menu.txt", { exact: true })).toBeVisible();
  await expect(cards.getByText("From notes.txt", { exact: true })).toBeVisible();
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("Menu item A");

  // The owner edited item A, so a replace that loses its document orphans it
  // instead of silently dropping the edit.
  await sheet.getByLabel("Offering 1 description").fill("Owner edit");
  await expect(sheet.getByLabel("Offering 1 description")).toHaveValue("Owner edit");

  await sheet.getByRole("button", { name: "Replace menu.txt" }).click();
  await sheet.getByTestId("review-replace-input").setInputFiles({
    name: "new.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("New contents"),
  });

  await expect.poll(() => records.deleteCount()).toBe(1);
  expect(records.deletedIds()).toEqual(["draft-1"]);

  // Old source gone, new source in; item A survives as an orphan, item B
  // keeps its provenance, the new document's candidate appends.
  await expect(sheet.getByText("menu.txt", { exact: true })).toHaveCount(0);
  await expect(sheet.getByText("new.txt", { exact: true })).toBeVisible();
  await expect(cards.getByText("From a replaced source", { exact: true })).toBeVisible();
  await expect(cards.getByText("From notes.txt", { exact: true })).toBeVisible();
  await expect(cards.getByText("From new.txt", { exact: true })).toBeVisible();
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("Menu item A");
  await expect(sheet.getByLabel("Offering 2 name")).toHaveValue("Menu item B");
  await expect(sheet.getByLabel("Offering 3 name")).toHaveValue("Menu item C");
});

test("batch publish keeps one failing document reviewable until it saves", async ({
  page,
  request,
}) => {
  const store = recordsStore([
    draftRecord({ id: "draft-1", filename: "menu.txt" }),
    draftRecord({ id: "draft-2", filename: "notes.txt" }),
  ]);
  await stubOnboardingState(page);
  await stubRecords(page, store);
  const batch = await stubBatch(page, store, {
    published: ["draft-1"],
    failed: [
      {
        document_id: "draft-2",
        error: "The price for screen repairs changed. Confirm it before saving.",
      },
    ],
    offering_candidates: [],
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  await sheet.getByTestId("onboarding-knowledge-save").click();

  // The published source left the review; the failing one stays with its
  // per-source error and the summary line, and confirm is still blocked.
  await expect(sheet.getByText("menu.txt", { exact: true })).toHaveCount(0);
  await expect(sheet.getByText("notes.txt", { exact: true })).toBeVisible();
  await expect(
    sheet.getByText("The price for screen repairs changed. Confirm it before saving."),
  ).toBeVisible();
  await expect(
    sheet.getByText("Some documents couldn't be saved. See the message under each source, then save again."),
  ).toBeVisible();
  await expect(page.getByTestId("onboarding-confirm")).toHaveCount(0);

  // A second save that publishes everything clears the workspace and opens
  // the confirm step. 29: that step is the server's call now - the client
  // re-reads state after a save instead of assuming a published review makes
  // the interview finishable - so the stub has to say so.
  await page.route("**/api/onboarding/state", (route) =>
    route.fulfill({ json: onboardingState({ can_confirm: true }) }),
  );
  batch.setResponse({ published: ["draft-1", "draft-2"], failed: [], offering_candidates: [] });
  await sheet.getByTestId("onboarding-knowledge-save").click();

  await expect(sheet.getByTestId("onboarding-knowledge-save")).toHaveCount(0);
  await expect(page.getByTestId("onboarding-confirm")).toBeVisible();
  await expect(page.getByTestId("onboarding-public-slug")).toHaveValue("test-repairs");
  await expect(page.getByTestId("onboarding-ready-card")).toHaveCount(0);
});

test("the category picker stays collapsed until its trigger is used", async ({ page, request }) => {
  const store = recordsStore([
    draftRecord({
      id: "draft-1",
      filename: "menu.txt",
      offering_candidates: [offeringCandidate("Menu item A", "draft-1", { price_cents: 1000 })],
    }),
  ]);
  await stubOnboardingState(page);
  await stubRecords(page, store);

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();

  // 31: one trigger, no picker in the DOM.
  const trigger = sheet.getByTestId("review-category-trigger");
  await expect(trigger).toHaveText("Add category");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(sheet.getByLabel("Search categories")).toHaveCount(0);

  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  const search = sheet.getByLabel("Search categories");
  await expect(search).toBeFocused();
  await expectInViewport(search);

  await sheet.getByTestId("review-category-done").click();
  await expect(sheet.getByLabel("Search categories")).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("removing an offering asks first, above the sheet, and cancel keeps it", async ({
  page,
  request,
}) => {
  const store = recordsStore([
    draftRecord({
      id: "draft-1",
      filename: "menu.txt",
      offering_candidates: [offeringCandidate("Menu item A", "draft-1", { price_cents: 1000 })],
    }),
  ]);
  await stubOnboardingState(page);
  await stubRecords(page, store);

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("Menu item A");

  await sheet.getByRole("button", { name: "Remove", exact: true }).click();
  const confirm = page.getByRole("dialog", { name: "Remove Menu item A?" });
  await expect(confirm).toBeVisible();
  await expect(confirm).toContainText("It will not be saved to your catalog.");
  // 31: the dialog is the page-level one, painted above the sheet's panel.
  const overlayZ = await confirm.evaluate(
    (node) => getComputedStyle(node.parentElement!).zIndex,
  );
  expect(overlayZ).toBe("60");

  await confirm.getByRole("button", { name: "Cancel" }).click();
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("Menu item A");

  // The last row of all: confirming removes it and focus lands on the action
  // that can add one back.
  await sheet.getByRole("button", { name: "Remove", exact: true }).click();
  await page.getByTestId("confirm-accept").click();
  await expect(sheet.getByLabel("Offering 1 name")).toHaveCount(0);
  await expect(sheet.getByText("No offerings yet.")).toBeVisible();
  await expect(sheet.getByRole("button", { name: "Add offering" })).toBeFocused();
});

test("removing a middle offering focuses the next row", async ({ page, request }) => {
  const candidates = Array.from({ length: 3 }, (_, i) =>
    offeringCandidate(`Item ${i + 1}`, "draft-1", { price_cents: 1000 }),
  );
  const store = recordsStore([
    draftRecord({ id: "draft-1", filename: "catalog.txt", offering_candidates: candidates }),
  ]);
  await stubOnboardingState(page);
  await stubRecords(page, store);

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  await sheet.getByRole("button", { name: "Remove", exact: true }).nth(1).click();
  await page.getByTestId("confirm-accept").click();

  // 31: the survivor moves up into the removed row and takes focus.
  await expect(sheet.getByLabel("Offering 2 name")).toHaveValue("Item 3");
  await expect(sheet.getByLabel("Offering 2 name")).toBeFocused();
});

test("removing the only row on the last page focuses the row above", async ({
  page,
  request,
}) => {
  const candidates = Array.from({ length: 6 }, (_, i) =>
    offeringCandidate(`Item ${i + 1}`, "draft-1", { price_cents: 1000 }),
  );
  const store = recordsStore([
    draftRecord({ id: "draft-1", filename: "catalog.txt", offering_candidates: candidates }),
  ]);
  await stubOnboardingState(page);
  await stubRecords(page, store);

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  await sheet.getByRole("button", { name: "Review all 6 offerings" }).click();
  await sheet.getByRole("button", { name: "Next" }).click();
  await expect(sheet.getByLabel("Offering 6 name")).toBeFocused();

  await sheet.getByRole("button", { name: "Remove", exact: true }).click();
  await page.getByTestId("confirm-accept").click();

  await expect(sheet.getByLabel("Offering 5 name")).toHaveValue("Item 5");
  await expect(sheet.getByLabel("Offering 5 name")).toBeFocused();
});

test("discarding from the footer asks, and cancel leaves the review open", async ({
  page,
  request,
}) => {
  const store = recordsStore([draftRecord({ id: "draft-1", filename: "menu.txt" })]);
  await stubOnboardingState(page);
  const records = await stubRecords(page, store);

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();

  await sheet.getByTestId("onboarding-knowledge-discard").click();
  const confirm = page.getByRole("dialog", { name: "Discard this source?" });
  await expect(confirm).toBeVisible();
  await expect(confirm).toContainText(
    "It is deleted, and its details and offerings are not saved.",
  );
  await expect(confirm.getByTestId("confirm-accept")).toHaveText("Discard source");

  await confirm.getByRole("button", { name: "Cancel" }).click();
  await expect(sheet).toBeVisible();
  expect(records.deleteCount()).toBe(0);

  await sheet.getByTestId("onboarding-knowledge-discard").click();
  await page.getByTestId("confirm-accept").click();
  await expect(sheet).toBeHidden();
  expect(records.deletedIds()).toEqual(["draft-1"]);
});

test("priced services lead and the source detail stays closed", async ({ page, request }) => {
  const candidates = Array.from({ length: 6 }, (_, i) =>
    offeringCandidate(`Item ${i + 1}`, "draft-1", {
      price_cents: i === 5 ? null : 1000,
    }),
  );
  const store = recordsStore([
    draftRecord({ id: "draft-1", filename: "catalog.txt", offering_candidates: candidates }),
  ]);
  await stubOnboardingState(page, {
    draft: { business_name: "Test Repairs", business_type: "phone repair shop" },
    missing_required: ["contact details"],
  });
  await stubRecords(page, store);

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();

  // 29: one missing price opens the list in edit mode on first paint and shows
  // the warning above the rows.
  await expect(sheet.getByRole("heading", { name: "What you offer" })).toBeVisible();
  await expect(sheet.getByTestId("review-missing-prices")).toHaveText(
    'No prices found here. Add a price, or write it your way, like "from $30".',
  );
  await expect(sheet.getByLabel("Offering 1 price")).toBeVisible();
  await expect(sheet.getByText("Page 1 of 2")).toBeVisible();

  // The business details the source found sit between the services and the
  // source line; the required gap is one note, not an empty row.
  await expect(sheet.getByTestId("review-profile-business_name")).toBeVisible();
  await expect(sheet.getByTestId("review-more-about-source")).toBeVisible();
  await expect(sheet.getByTestId("review-missing-required")).toHaveText(
    "I'll ask next: contact details.",
  );

  // 31: every review field uses the console recipe - 16px text, at least the
  // 44px floor, and the field radius - and the card stack keeps the 8px step.
  const fieldFacts = async (label: string) =>
    sheet.getByLabel(label).evaluate((node) => {
      const style = getComputedStyle(node);
      return {
        fontSize: style.fontSize,
        height: node.getBoundingClientRect().height,
        radius: style.borderRadius,
      };
    });
  const fieldRadius = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--radius-field").trim(),
  );
  const offeringFacts = await fieldFacts("Offering 1 name");
  expect(offeringFacts.fontSize).toBe("16px");
  expect(offeringFacts.height).toBeGreaterThanOrEqual(44);
  expect(offeringFacts.radius).toBe(fieldRadius);
  const firstCard = await sheet.locator("article").nth(0).boundingBox();
  const secondCard = await sheet.locator("article").nth(1).boundingBox();
  expect(secondCard!.y - (firstCard!.y + firstCard!.height)).toBeCloseTo(8, 0);
  const introBottom = (await sheet.getByText(/Here's what I found in/).boundingBox())!;
  const offeringsTop = (await sheet
    .getByRole("heading", { name: "What you offer" })
    .locator("..")
    .boundingBox())!;
  expect(offeringsTop.y - (introBottom.y + introBottom.height)).toBeCloseTo(16, 0);

  await sheet.getByTestId("review-profile-edit-business_name").click();
  const profileFacts = await fieldFacts("Business name");
  expect(profileFacts.fontSize).toBe("16px");
  expect(profileFacts.height).toBeGreaterThanOrEqual(44);
  expect(profileFacts.radius).toBe(fieldRadius);

  // The structured sections and the source text are not inline by default.
  await expect(sheet.getByText("9 to 5, Monday to Friday")).toHaveCount(0);
  await expect(
    sheet.getByText("Original extracted source. It does not answer customers."),
  ).toHaveCount(0);

  await sheet.getByTestId("review-more-about-source").click();
  await expect(sheet.getByText("9 to 5, Monday to Friday")).toBeVisible();
  await expect(
    sheet.getByText("Original extracted source. It does not answer customers."),
  ).toHaveCount(0);
});

test("pagination and toolbar keep review stable while typing", async ({ page, request }) => {
  // Priced on purpose: a fully priced catalog keeps the collapsed default, so
  // this spec still exercises the review-all path. The missing-price open
  // behaviour has its own spec below.
  const candidates = Array.from({ length: 12 }, (_, i) =>
    offeringCandidate(`Item ${i + 1}`, "draft-1", { price_cents: 1000 }),
  );
  const store = recordsStore([
    draftRecord({ id: "draft-1", filename: "catalog.txt", offering_candidates: candidates }),
  ]);
  await stubOnboardingState(page);
  await stubRecords(page, store);

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();

  // Collapsed on desktop: five read-only cards, no pagination rows, and both
  // actions sit below the last visible card.
  await expect(sheet.getByText("Page 1 of 3")).toHaveCount(0);
  await expect(sheet.getByText("Showing 1-5 of 12 offerings")).toHaveCount(0);
  for (const name of ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"]) {
    await expect(sheet.getByText(name, { exact: true })).toBeVisible();
  }
  await expect(sheet.getByText("Item 6", { exact: true })).toHaveCount(0);

  const reviewAll = sheet.getByRole("button", { name: "Review all 12 offerings" });
  const addOffering = sheet.getByRole("button", { name: "Add offering" });
  await expect(reviewAll).toBeVisible();
  const lastCardBox = await sheet.getByText("Item 5", { exact: true }).boundingBox();
  const reviewAllBox = await reviewAll.boundingBox();
  const addBox = await addOffering.boundingBox();
  expect(reviewAllBox!.y).toBeGreaterThan(lastCardBox!.y);
  expect(addBox!.y).toBeGreaterThan(lastCardBox!.y);

  await reviewAll.click();
  await expect(sheet.getByText("Page 1 of 3")).toBeVisible();
  await expect(sheet.getByText("Showing 1-5 of 12 offerings")).toBeVisible();
  // 31: expanding lands focus on the row it revealed.
  await expect(sheet.getByLabel("Offering 1 name")).toBeFocused();

  await sheet.getByRole("button", { name: "Next" }).click();
  await expect(sheet.getByText("Page 2 of 3")).toBeVisible();
  await expect(sheet.getByText("Showing 6-10 of 12 offerings")).toBeVisible();
  // 31: paging moves focus to the first row of the new page and scrolls it in.
  await expect(sheet.getByLabel("Offering 6 name")).toBeFocused();
  await expectInViewport(sheet.getByLabel("Offering 6 name"));

  await sheet.getByRole("button", { name: "Next" }).click();
  await expect(sheet.getByText("Page 3 of 3")).toBeVisible();
  await expect(sheet.getByText("Showing 11-12 of 12 offerings")).toBeVisible();
  await expect(sheet.getByLabel("Offering 11 name")).toBeFocused();
  await expectInViewport(sheet.getByLabel("Offering 11 name"));

  await sheet.getByRole("button", { name: "Previous" }).click();
  await expect(sheet.getByLabel("Offering 6 name")).toBeFocused();
  await sheet.getByRole("button", { name: "Previous" }).click();
  await expect(sheet.getByText("Page 1 of 3")).toBeVisible();
  await expect(sheet.getByLabel("Offering 1 name")).toBeFocused();

  // Typing in an offering never changes the page.
  await sheet.getByLabel("Offering 1 name").fill("Renamed item");
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("Renamed item");
  await expect(sheet.getByText("Page 1 of 3")).toBeVisible();

  // Add offering jumps to the page holding the new owner row and focuses it.
  await sheet.getByRole("button", { name: "Next" }).click();
  await sheet.getByRole("button", { name: "Next" }).click();
  await expect(sheet.getByText("Page 3 of 3")).toBeVisible();
  await addOffering.click();
  await expect(sheet.getByText("Page 1 of 3")).toBeVisible();
  await expect(sheet.getByLabel("Offering 1 name")).toBeFocused();
  await expectInViewport(sheet.getByLabel("Offering 1 name"));
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("");

  // Escape closes the sheet; the ready card is the way back in. Focus is
  // already inside the sheet on the new offering row above.
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("onboarding-ready-card")).toBeVisible();
});
/** 31: a URL source row, addressed by its host label. */
function websiteRecord(overrides: Parameters<typeof draftRecord>[0] = {}) {
  return draftRecord({
    id: "site-1",
    filename: "https://old.example.com/menu",
    doc_type: "website",
    offering_candidates: [offeringCandidate("Menu item A", "site-1")],
    ...overrides,
  });
}

test("editing a link and cancelling leaves the source alone", async ({ page, request }) => {
  const store = recordsStore([websiteRecord()]);
  await stubOnboardingState(page);
  const records = await stubRecords(page, store);
  const sourceUrl = await stubSourceUrl(page, store, {
    recordFor: (url) => websiteRecord({ filename: url }),
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  const opener = sheet.getByTestId("review-edit-link");
  await expect(opener).toHaveAttribute("aria-label", "Edit link for old.example.com");

  await opener.click();
  const input = sheet.getByTestId("review-link-input");
  await expect(input).toHaveValue("https://old.example.com/menu");
  await expect(input).toBeFocused();
  await expectInViewport(input);

  await sheet.getByLabel("Cancel link").click();
  await expect(sheet.getByTestId("review-link-input")).toHaveCount(0);
  await expect(opener).toBeFocused();
  // The review is still open, the source is still there, and no request ran.
  await expect(sheet).toBeVisible();
  await expect(sheet.getByText("old.example.com", { exact: true })).toBeVisible();
  await expect(sheet.getByTestId("review-edit-link")).toHaveCount(1);
  expect(sourceUrl.calls()).toHaveLength(0);
  expect(records.deletedIds()).toHaveLength(0);
});

test("saving the same link re-reads one source in place", async ({ page, request }) => {
  const store = recordsStore([websiteRecord()]);
  await stubOnboardingState(page);
  const records = await stubRecords(page, store);
  const sourceUrl = await stubSourceUrl(page, store, {
    recordFor: (url) => websiteRecord({ filename: url }),
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  await sheet.getByTestId("review-edit-link").click();
  await sheet.getByLabel("Save link").click();

  const confirm = page.getByRole("dialog", { name: "Replace this link?" });
  await expect(confirm).toBeVisible();
  await page.getByTestId("confirm-accept").click();

  await expect.poll(() => sourceUrl.calls().length).toBe(1);
  expect(sourceUrl.calls()[0]).toEqual({
    url: "https://old.example.com/menu",
    replace_document_id: "site-1",
  });
  await expect(sheet.getByTestId("review-link-input")).toHaveCount(0);
  // Same address, same row: one source, one id, nothing deleted.
  expect(store.records.map((record) => record.id)).toEqual(["site-1"]);
  expect(records.deletedIds()).toHaveLength(0);
  await expect(sheet.getByText("old.example.com", { exact: true })).toBeVisible();
  await expect(sheet.getByTestId("review-edit-link")).toHaveCount(1);
});

test("saving a different link replaces the source", async ({ page, request }) => {
  const store = recordsStore([websiteRecord()]);
  await stubOnboardingState(page);
  const records = await stubRecords(page, store);
  const sourceUrl = await stubSourceUrl(page, store, {
    recordFor: (url) =>
      websiteRecord({
        id: "site-2",
        filename: url,
        offering_candidates: [offeringCandidate("Menu item A", "site-2")],
      }),
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  await expect(sheet.getByText("old.example.com", { exact: true })).toBeVisible();

  await sheet.getByTestId("review-edit-link").click();
  const input = sheet.getByTestId("review-link-input");
  await input.fill("https://new.example.com/menu");
  await sheet.getByLabel("Save link").click();

  // The replacement asks first; cancelling it makes no request.
  const confirm = page.getByRole("dialog", { name: "Replace this link?" });
  await expect(confirm).toBeVisible();
  await expect(confirm).toContainText(
    "The new site will be read, and its details and offerings will replace this source.",
  );
  await expect(confirm.getByTestId("confirm-accept")).toHaveText("Replace link");
  await confirm.getByRole("button", { name: "Cancel" }).click();
  expect(sourceUrl.calls()).toHaveLength(0);
  await expect(input).toHaveValue("https://new.example.com/menu");

  await sheet.getByLabel("Save link").click();
  await page.getByTestId("confirm-accept").click();

  await expect.poll(() => sourceUrl.calls().length).toBe(1);
  expect(sourceUrl.calls()[0]).toEqual({
    url: "https://new.example.com/menu",
    replace_document_id: "site-1",
  });
  await expect(sheet.getByText("old.example.com", { exact: true })).toHaveCount(0);
  await expect(sheet.getByText("new.example.com", { exact: true })).toBeVisible();
  expect(records.deletedIds()).toEqual(["site-1"]);
  expect(store.records.map((record) => record.id)).toEqual(["site-2"]);
});

test("add a link adds a second source and focuses the editor", async ({ page, request }) => {
  const store = recordsStore([draftRecord({ id: "draft-1", filename: "menu.txt" })]);
  await stubOnboardingState(page);
  const records = await stubRecords(page, store);
  const sourceUrl = await stubSourceUrl(page, store, {
    recordFor: (url) =>
      draftRecord({
        id: "site-2",
        filename: url,
        doc_type: "website",
        offering_candidates: [offeringCandidate("Online item", "site-2")],
      }),
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const sheet = dialog(page);
  await expect(sheet).toBeVisible();
  await sheet.getByTestId("review-add-link").click();

  const input = sheet.getByTestId("review-link-input");
  await expect(input).toHaveValue("");
  await expect(input).toBeFocused();
  await expectInViewport(input);

  await input.fill("https://bytefix.example.com");
  await sheet.getByLabel("Save link").click();

  await expect(sheet.getByText("bytefix.example.com", { exact: true })).toBeVisible();
  // Two source rows now: the file keeps its picker, the link its editor.
  await expect(sheet.getByTestId("review-remove-source")).toHaveCount(2);
  await expect(sheet.getByTestId("review-edit-link")).toHaveCount(1);
  await expect(sheet.getByTestId("review-link-input")).toHaveCount(0);
  expect(sourceUrl.calls()).toEqual([
    { url: "https://bytefix.example.com", replace_document_id: null },
  ]);
  expect(records.deletedIds()).toHaveLength(0);
});
