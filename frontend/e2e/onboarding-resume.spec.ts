/**
 * E2E for the resumable-input slice of the onboarding refinement ticket.
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * What only a browser can prove here: the knowledge decline survives a reload
 * (the client reads what it lands on from the server's checkpoint, not from
 * state it kept in memory), and rejecting a proposed name costs no server turn -
 * the composer is prefilled and focused in the browser. The route stubs are
 * stateful, the way knowledge-review-mocks.ts stubs are, so the reload sees the
 * world the skip left behind rather than a canned reply.
 */

import { expect, test, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";
import { onboardingState, textInputSpec } from "./knowledge-review-mocks";

const BYTEFIX = DEMO_USERS[0];

/** The composer for the beat on screen. */
function composer(page: Page) {
  return page.getByTestId("onboarding-composer");
}

test("the knowledge Skip chip closes the ask across a reload", async ({ page, request }) => {
  // 20: the knowledge ask is the one place a Skip chip survives, because it is
  // the one step that never gates go-live. The server's checkpoint is a test
  // double: the decline mutates it, and the reload's GET reads it back.
  const checkpoint = {
    stage: "knowledge",
    prompt: "Do you have a website or any documents?",
    revision: 4,
    can_confirm: false,
    history: [{ role: "assistant", content: "Do you have a website or any documents?" }],
  };
  const skipChip = {
    label: "Skip for now",
    value: "skip",
    dashed: true,
    widget: null,
  };
  function serve() {
    return onboardingState({
      stage: checkpoint.stage,
      prompt: checkpoint.prompt,
      revision: checkpoint.revision,
      can_confirm: checkpoint.can_confirm,
      history: checkpoint.history,
      // Only the knowledge ask offers the chip, so the reload proves the ask
      // closed rather than proving the stub always sends the same chips.
      input:
        checkpoint.stage === "knowledge"
          ? { ...textInputSpec("Paste a link or attach a file…"), chips: [skipChip] }
          : null,
    });
  }

  await page.route("**/api/onboarding/state", (route) => route.fulfill({ json: serve() }));

  const selections: unknown[] = [];
  await page.route("**/api/onboarding/message", (route) => {
    selections.push(JSON.parse(route.request().postData() ?? "{}"));
    checkpoint.stage = "confirm";
    checkpoint.prompt = "Your assistant is ready to go live.";
    checkpoint.can_confirm = true;
    checkpoint.revision += 1;
    checkpoint.history = [
      ...checkpoint.history,
      { role: "user", content: "Skip for now" },
      { role: "assistant", content: "Your assistant is ready to go live." },
    ];
    return route.fulfill({ json: serve() });
  });

  await loginAsTenantAdmin(page, request, BYTEFIX);

  await expect(composer(page).getByTestId("onboarding-chip-skip")).toBeVisible();
  await composer(page).getByTestId("onboarding-chip-skip").click();

  // The decline travels as a selection on the ask itself, the same shape any
  // chip sends - there is no separate skip verb on the payload any more.
  await expect
    .poll(() => selections)
    .toEqual([{ selection: { beat: "knowledge", values: ["skip"] } }]);

  const thread = page.getByTestId("onboarding-thread");
  await expect(thread).toContainText("ready to go live");

  // The reload is the point: nothing is carried over in the client, so what is
  // on screen is whatever the checkpoint says it is.
  await page.reload();
  await expect(thread).toContainText("ready to go live");
  // The decline is in the transcript, and the ask is not repeated.
  await expect(thread).toContainText("Skip for now");
  await expect(composer(page).getByTestId("onboarding-chip-skip")).toHaveCount(0);
});

test("saying No to a proposed name prefills the composer without a server turn", async ({
  page,
  request,
}) => {
  const proposal = "Bytefix Repairs";
  await page.route("**/api/onboarding/state", (route) =>
    route.fulfill({
      json: onboardingState({
        stage: "business_name",
        prompt: `Should I save the business name as "${proposal}"?`,
        history: [
          { role: "assistant", content: `Should I save the business name as "${proposal}"?` },
        ],
        pending_confirmation: { target: "business_name", raw: proposal, proposal },
        input: {
          ...textInputSpec("Yes, or type the correction"),
          chips: [
            { label: "Yes", value: "yes", dashed: false, widget: null },
            { label: "No", value: "no", dashed: false, widget: null },
          ],
        },
      }),
    }),
  );

  // Every way a turn could leave the browser, counted. The No chip must use none.
  let turns = 0;
  await page.route("**/api/onboarding/message", (route) => {
    turns += 1;
    return route.fulfill({ json: onboardingState() });
  });
  await page.route("**/api/onboarding/message/stream", (route) => {
    turns += 1;
    return route.fulfill({ contentType: "text/event-stream", body: 'data: {"type":"done"}\n\n' });
  });

  await loginAsTenantAdmin(page, request, BYTEFIX);

  await composer(page).getByTestId("onboarding-chip-no").click();

  const textbox = composer(page).getByRole("textbox");
  await expect(textbox).toHaveValue(proposal);
  // Prefilled is only half of it - the cursor has to be in the box, or the
  // owner's next keystroke goes nowhere.
  await expect(textbox).toBeFocused();
  expect(turns).toBe(0);
});

test("the Home suggestions card reviews the private drafts and publishes them", async ({
  page,
  request,
}) => {
  const candidates = [
    {
      candidate_id: "cand-screen-repair",
      name: "Screen repair",
      description: "Same-day for most phones",
      price_cents: 12900,
      sources: ["document"],
      review_status: "pending",
    },
    {
      candidate_id: "cand-battery-swap",
      name: "Battery swap",
      description: "",
      price_cents: null,
      sources: ["document"],
      review_status: "pending",
    },
  ];
  let published: { candidates: { name: string; review_status?: string }[] } | null = null;
  await page.route("**/api/onboarding/suggestions", (route) => {
    if (route.request().method() === "PUT") {
      published = JSON.parse(route.request().postData() ?? "{}");
      return route.fulfill({ json: { count: 0, candidates: [] } });
    }
    return route.fulfill({ json: { count: candidates.length, candidates } });
  });

  await loginAsTenantAdmin(page, request, BYTEFIX);
  await page.goto("/home");

  await page.getByRole("button", { name: "Review suggestions" }).click();
  await expect(page.getByRole("heading", { name: "Suggestions to review" })).toBeVisible();
  await expect(
    page.getByText("These private drafts never reach customers until you save them."),
  ).toBeVisible();

  await page.getByTestId("suggestions-save").click();

  // The whole point of the sheet: nothing is approved until the owner says so,
  // and then everything in it is.
  await expect.poll(() => published).not.toBeNull();
  expect(published!.candidates.map((item) => item.name)).toEqual([
    "Screen repair",
    "Battery swap",
  ]);
  expect(published!.candidates.every((item) => item.review_status === "approved")).toBe(true);

  await expect(page.getByText("Suggestions saved")).toBeVisible();
  // Nothing is waiting any more, so the card is gone rather than showing zero.
  await expect(page.getByRole("button", { name: "Review suggestions" })).toHaveCount(0);
});

test("the Home suggestions sheet asks before removing a suggestion", async ({
  page,
  request,
}) => {
  const candidates = [
    {
      candidate_id: "cand-screen-repair",
      name: "Screen repair",
      description: "",
      price_cents: null,
      sources: ["document"],
      review_status: "pending",
    },
    {
      candidate_id: "cand-battery-swap",
      name: "Battery swap",
      description: "",
      price_cents: null,
      sources: ["document"],
      review_status: "pending",
    },
  ];
  let puts = 0;
  await page.route("**/api/onboarding/suggestions", (route) => {
    if (route.request().method() === "PUT") {
      puts += 1;
      return route.fulfill({ json: { count: 0, candidates: [] } });
    }
    return route.fulfill({ json: { count: candidates.length, candidates } });
  });

  await loginAsTenantAdmin(page, request, BYTEFIX);
  await page.goto("/home");
  await page.getByRole("button", { name: "Review suggestions" }).click();

  const sheet = page.getByRole("dialog", { name: "Suggestions to review" });
  await expect(sheet).toBeVisible();
  await sheet.getByRole("button", { name: "Remove", exact: true }).first().click();

  const confirm = page.getByRole("dialog", { name: "Remove Screen repair?" });
  await expect(confirm).toBeVisible();
  await expect(confirm).toContainText("It will not be saved to your catalog.");
  await confirm.getByRole("button", { name: "Cancel" }).click();
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("Screen repair");
  await expect(sheet.getByLabel("Offering 2 name")).toHaveValue("Battery swap");

  await sheet.getByRole("button", { name: "Remove", exact: true }).first().click();
  await page.getByTestId("confirm-accept").click();
  await expect(sheet.getByLabel("Offering 1 name")).toHaveValue("Battery swap");
  expect(puts).toBe(0);
});

test("paging the suggestions sheet still sends every candidate on save", async ({
  page,
  request,
}) => {
  const candidates = Array.from({ length: 9 }, (_, index) => ({
    candidate_id: `cand-${index + 1}`,
    name: `Suggestion ${index + 1}`,
    description: "",
    price_cents: null,
    sources: ["document"],
    review_status: "pending",
  }));
  let published: { candidates: { name: string; review_status?: string }[] } | null = null;
  await page.route("**/api/onboarding/suggestions", (route) => {
    if (route.request().method() === "PUT") {
      published = JSON.parse(route.request().postData() ?? "{}");
      return route.fulfill({ json: { count: 0, candidates: [] } });
    }
    return route.fulfill({ json: { count: candidates.length, candidates } });
  });

  await loginAsTenantAdmin(page, request, BYTEFIX);
  await page.goto("/home");
  await page.getByRole("button", { name: "Review suggestions" }).click();

  const sheet = page.getByRole("dialog", { name: "Suggestions to review" });
  await expect(sheet.getByText("Showing 1-5 of 9 suggestions")).toBeVisible();
  await sheet.getByRole("button", { name: "Next" }).click();
  await expect(sheet.getByText("Showing 6-9 of 9 suggestions")).toBeVisible();

  // 31: the save is the whole list, never the visible page.
  await page.getByTestId("suggestions-save").click();
  await expect.poll(() => published).not.toBeNull();
  expect(published!.candidates.map((item) => item.name)).toEqual(
    candidates.map((item) => item.name),
  );
  expect(published!.candidates.every((item) => item.review_status === "approved")).toBe(true);
});
