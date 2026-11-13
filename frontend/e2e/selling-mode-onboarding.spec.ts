import { expect, test, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";
import { recordsStore, stubRecords } from "./knowledge-review-mocks";
import { mockQueue } from "./queue-fixtures";

/**
 * 32 slice A: the selling-mode question, at the surface.
 *
 * The onboarding server is a small state machine, the way
 * onboarding-source-first.spec.ts builds one: every route records what it was
 * asked and hands the decision to the test, so a client that reads the wrong
 * stage after a turn fails on the next assertion instead of passing on a canned
 * reply. No real model runs - this flow is deterministic by design, and the one
 * inference it shows is the server's payload, stubbed here at its contract.
 *
 * The run: name -> source -> the inferred mode card -> confirm or correct ->
 * the read-back from what was stored -> go live, then the owner's Home naming
 * the Work destination the way their labels do.
 */

interface Chip {
  label: string;
  value: string;
  dashed?: boolean;
  widget?: string | null;
}

interface Input {
  kind: "text";
  placeholder: string;
  chips: Chip[];
  mask: null;
  cta_label: null;
  prefix: null;
  suggest_owner_email: false;
}

interface SellingModePayload {
  mode: string;
  capabilities: Record<string, unknown>;
  labels: Record<string, string>;
  defaults?: Record<string, number | string>;
  confidence: string;
  candidates: string[];
  evidence: string[];
  summary: string;
}

interface ServerState {
  stage: string;
  prompt: string;
  draft: Record<string, string | string[]>;
  completed: boolean;
  history: { role: string; content: string }[];
  input: Input | null;
  can_confirm: boolean;
  suggested_slug: string | null;
  paused_beat: null;
  selling_mode?: SellingModePayload | null;
}

interface Selection {
  beat: string;
  values: string[];
}

const ORDERS_SUMMARY =
  "Your assistant will take orders from your menu, offer eat in and pickup, " +
  "mark a dish sold out when you run out, and take payment up front. " +
  "You can change this later.";

const BOOKINGS_SUMMARY =
  "Your assistant will take bookings for your services, offer on-site visits, " +
  "offer time slots and let them pay later. You can change this later.";

function textInput(overrides: Partial<Input> = {}): Input {
  return {
    kind: "text",
    placeholder: "",
    chips: [],
    mask: null,
    cta_label: null,
    prefix: null,
    suggest_owner_email: false,
    ...overrides,
  };
}

function view(stage: string, overrides: Partial<ServerState> = {}): ServerState {
  return {
    stage,
    prompt: "",
    draft: {},
    completed: false,
    history: [],
    input: null,
    can_confirm: false,
    suggested_slug: null,
    paused_beat: null,
    ...overrides,
  };
}

function nameStage(): ServerState {
  return view("owner_display_name", {
    prompt: "Before we start, what should I call you?",
    input: textInput(),
    history: [{ role: "assistant", content: "Before we start, what should I call you?" }],
  });
}

function sourceStage(history: ServerState["history"]): ServerState {
  return view("knowledge", {
    prompt: "Do you have a website or any documents?",
    input: textInput({
      placeholder: "Paste a link or attach a file\u2026",
      chips: [{ label: "Skip for now", value: "skip", dashed: true, widget: null }],
    }),
    history,
  });
}

/** The inference the real endpoint would answer with for a menu source. */
function sellingModeStage(history: ServerState["history"]): ServerState {
  return view("selling_mode", {
    prompt: "How do customers buy from you?",
    input: textInput(),
    history,
    selling_mode: {
      mode: "orders",
      capabilities: {
        sell: ["orders"],
        schedule: "asap",
        stock: "flag",
        fulfillment: ["in_house", "pickup"],
        acceptance: "auto",
        payment: "now",
      },
      labels: {
        item: "Dish",
        items: "Menu",
        work: "Orders",
        add_item: "Add a dish",
        time: "Prep time",
        sold_out: "Sold out today",
        action: "Order",
      },
      defaults: { lead_time_minutes: 30, hold_ttl_minutes: 15 },
      confidence: "high",
      candidates: ["orders"],
      evidence: ['"menu" in your website', '"order online" in your website'],
      summary: ORDERS_SUMMARY,
    },
  });
}

/**
 * The confirm screen's card: the stored config, read back by the server.
 *
 * `summary` is the sentence the owner approves before go-live, so it names what
 * was saved - the corrected bookings bundle here - and never the inference the
 * interview opened on.
 */
function storedModeStage(
  mode: "orders" | "bookings",
  history: ServerState["history"],
): ServerState {
  const bookings = mode === "bookings";
  return view("confirm", {
    draft: { business_name: bookings ? "Fresh Cuts" : "Sababa" },
    can_confirm: true,
    suggested_slug: bookings ? "fresh-cuts" : "sababa",
    history,
    selling_mode: {
      mode,
      capabilities: bookings
        ? {
            sell: ["bookings"],
            schedule: "slot",
            stock: "none",
            fulfillment: ["onsite"],
            acceptance: "auto",
            payment: "later",
          }
        : {
            sell: ["orders"],
            schedule: "asap",
            stock: "flag",
            fulfillment: ["in_house", "pickup"],
            acceptance: "auto",
            payment: "now",
          },
      labels: bookings
        ? {
            item: "Service",
            items: "Services",
            work: "Bookings",
            add_item: "Add a service",
            time: "Duration",
            sold_out: "Unavailable",
            action: "Book",
          }
        : {
            item: "Dish",
            items: "Menu",
            work: "Orders",
            add_item: "Add a dish",
            time: "Prep time",
            sold_out: "Sold out today",
            action: "Order",
          },
      defaults: {
        lead_time_minutes: bookings ? 45 : 30,
        hold_ttl_minutes: 15,
        owner_hold_ttl_minutes: 30,
        slot_increment_minutes: 15,
        deposit_bps: 0,
        timezone: "Australia/Sydney",
        delivery_fee_cents: 0,
        delivery_radius_km: 0,
      },
      confidence: "high",
      candidates: [mode],
      evidence: [],
      summary: bookings ? BOOKINGS_SUMMARY : ORDERS_SUMMARY,
    },
  });
}

interface Flow {
  state: ServerState;
  selections: Selection[];
  texts: string[];
  postedModes: Record<string, unknown>[];
  confirmSlugs: string[];
  onSelection(selection: Selection): ServerState;
  onText(text: string): { reply: string; state: ServerState };
  onSellingMode(body: Record<string, unknown>): ServerState;
}

/**
 * The onboarding server for this run. The selling-mode collection answers both
 * verbs, so its route is one handler: a GET returns what was stored, a POST
 * writes and advances - and a query string can only ever land on the GET, which
 * a glob would have missed.
 */
async function installFlow(page: Page, start: ServerState): Promise<Flow> {
  const selections: Selection[] = [];
  const texts: string[] = [];
  const postedModes: Record<string, unknown>[] = [];
  const confirmSlugs: string[] = [];

  const flow: Flow = {
    state: start,
    selections,
    texts,
    postedModes,
    confirmSlugs,
    onSelection: () => flow.state,
    onText: (text) => ({ reply: `Got it: ${text}`, state: flow.state }),
    onSellingMode: () => flow.state,
  };

  await page.route("**/api/onboarding/state", (route) => route.fulfill({ json: flow.state }));
  await page.route("**/api/onboarding/message", async (route) => {
    const body = route.request().postDataJSON() as { selection?: Selection };
    if (body.selection) {
      selections.push(body.selection);
      flow.state = flow.onSelection(body.selection);
    }
    await route.fulfill({ json: flow.state });
  });
  await page.route("**/api/onboarding/message/stream", async (route) => {
    const text = (route.request().postDataJSON() as { text: string }).text;
    texts.push(text);
    const next = flow.onText(text);
    flow.state = next.state;
    await route.fulfill({
      contentType: "text/event-stream",
      body: [
        `data: ${JSON.stringify({ type: "reply", text: next.reply })}`,
        `data: ${JSON.stringify({ type: "state", ...next.state })}`,
        'data: {"type":"done"}',
        "",
      ].join("\n\n"),
    });
  });
  // One handler for both verbs, because the collection is one path: the POST
  // answers the state the client applies directly, and the GET is the stored
  // block for anything that asks (nothing on this screen does any more).
  await page.route("**/api/onboarding/selling-mode*", async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill({ json: { config: null, summary: null } });
      return;
    }
    const body = request.postDataJSON() as Record<string, unknown>;
    postedModes.push(body);
    flow.state = flow.onSellingMode(body);
    await route.fulfill({ json: flow.state });
  });
  await page.route("**/api/onboarding/confirm", async (route) => {
    confirmSlugs.push((route.request().postDataJSON() as { slug: string }).slug);
    await route.fulfill({ json: { tenant_id: "tenant-1", slug: "bytefix" } });
  });

  return flow;
}

test("the owner corrects the inferred mode and goes live", async ({ page, request }) => {
  await stubRecords(page, recordsStore([]));
  await mockQueue(page, []);
  await page.route("**/api/tenants/me", (route) =>
    route.fulfill({
      json: {
        tenant_id: "00000000-0000-4000-8000-000000000001",
        slug: "bytefix",
        name: "Bytefix",
        brand: {},
        ordering: {
          mode: "bookings",
          capabilities: {
            sell: ["bookings"],
            schedule: "slot",
            stock: "none",
            fulfillment: ["onsite"],
            acceptance: "auto",
            payment: "later",
          },
          labels: {
            item: "Service",
            items: "Services",
            work: "Bookings",
            add_item: "Add a service",
            time: "Duration",
            sold_out: "Unavailable",
            action: "Book",
          },
          defaults: {},
        },
      },
    }),
  );

  const flow = await installFlow(page, nameStage());

  flow.onSelection = (selection) => {
    expect(selection).toEqual({ beat: "knowledge", values: ["skip"] });
    return sellingModeStage([
      { role: "assistant", content: "Before we start, what should I call you?" },
      { role: "user", content: "skip" },
      { role: "assistant", content: "No problem. Do you have a website or any documents?" },
      { role: "user", content: "Skip for now" },
      { role: "assistant", content: "No problem. How do customers buy from you?" },
    ]);
  };
  flow.onSellingMode = (body) => {
    // The correction is what the owner picked, not what was inferred.
    expect(body.mode).toBe("bookings");
    expect((body.capabilities as { sell: string[] }).sell).toEqual(["bookings"]);
    expect((body.labels as Record<string, string>).work).toBe("Bookings");
    // The timing row wrote the real default, not a client-side copy of it.
    expect((body.defaults as Record<string, number>).lead_time_minutes).toBe(45);
    return view("business_name", {
      prompt: "What does the business go by?",
      input: textInput(),
      history: [
        { role: "assistant", content: "No problem. How do customers buy from you?" },
        { role: "user", content: "Bookings" },
        { role: "assistant", content: "Got it. What does the business go by?" },
      ],
      selling_mode: null,
    });
  };
  flow.onText = (text) => {
    if (text === "skip") {
      return {
        reply: "No problem. Do you have a website or any documents?",
        state: sourceStage([
          { role: "assistant", content: "Before we start, what should I call you?" },
          { role: "user", content: "skip" },
          { role: "assistant", content: "No problem. Do you have a website or any documents?" },
        ]),
      };
    }
    expect(text).toBe("Fresh Cuts");
    return {
      reply: "Got it. Your assistant is ready to go live.",
      state: storedModeStage("bookings", [
        { role: "assistant", content: "Got it. What does the business go by?" },
        { role: "user", content: "Fresh Cuts" },
        { role: "assistant", content: "Got it. Your assistant is ready to go live." },
      ]),
    };
  };

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  const thread = page.getByTestId("onboarding-thread");
  await expect(thread).toBeVisible();

  const composer = page.getByTestId("onboarding-composer");

  // 1. The name, then the source - both skipped, as in the source-first spec.
  await composer.getByRole("textbox").fill("skip");
  await composer.getByRole("button", { name: "Send" }).click();
  await expect.poll(() => flow.texts).toEqual(["skip"]);

  await expect(composer.getByRole("button", { name: "Skip for now" })).toBeVisible();
  await composer.getByRole("button", { name: "Skip for now" }).click();
  await expect.poll(() => flow.selections).toEqual([{ beat: "knowledge", values: ["skip"] }]);

  // 2. The inferred mode, with the evidence it scored and the server's summary.
  const card = page.getByTestId("selling-mode-card");
  await expect(card).toBeVisible();
  await expect(page.getByTestId("selling-mode-headline")).toHaveText(
    "It looks like customers order from you.",
  );
  await expect(page.getByTestId("selling-mode-summary")).toHaveText(ORDERS_SUMMARY);
  await expect(page.getByTestId("selling-mode-evidence")).toContainText('"menu" in your website');
  await expect(page.getByTestId("selling-mode-confirm")).toBeVisible();

  // 3. The change path opens on the proposal, and the follow-ups are the ones
  //    Orders actually has: a timing row, stock, and no approval.
  await page.getByTestId("selling-mode-change").click();
  await expect(page.getByTestId("selling-mode-lead-time-30")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByTestId("selling-mode-stock-flag")).toBeVisible();
  await expect(page.getByTestId("selling-mode-acceptance-auto")).toHaveCount(0);
  await page.getByTestId("selling-mode-lead-time-45").click();

  // 4. One tap corrects it: pick Bookings, drop the inferred Orders, save. The
  //    multi-select starts from the proposal, so "instead of Orders" is two
  //    taps rather than a hidden replacement - and the rows follow the picks.
  await page.getByTestId("selling-mode-pick-bookings").click();
  await page.getByTestId("selling-mode-pick-orders").click();
  await expect(page.getByTestId("selling-mode-schedule-slot")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByTestId("selling-mode-acceptance-auto")).toBeVisible();
  await expect(page.getByTestId("selling-mode-stock-flag")).toHaveCount(0);
  await expect(page.getByTestId("selling-mode-lead-time-30")).toHaveCount(0);
  await page.getByTestId("selling-mode-save").click();

  await expect.poll(() => flow.postedModes.length).toBe(1);

  // 5. The POST's own state is applied: the card is gone and the next question
  //    is on screen - no second read, nothing to retry into a duplicate.
  await expect(page.getByTestId("selling-mode-card")).toHaveCount(0);
  await expect(composer.getByRole("textbox")).toBeVisible();
  await composer.getByRole("textbox").fill("Fresh Cuts");
  await composer.getByRole("button", { name: "Send" }).click();

  // 6. The confirm screen reads the stored config back: the summary names the
  //    corrected capabilities, not the orders the source suggested.
  await expect(page.getByTestId("onboarding-confirm")).toBeVisible();
  const summary = page.getByTestId("onboarding-selling-summary");
  await expect(summary).toContainText(BOOKINGS_SUMMARY);
  await expect(summary).toContainText("take bookings for your services");
  await expect(summary).not.toContainText("take orders");
  await expect(page.getByTestId("onboarding-public-slug")).toHaveValue("fresh-cuts");
  await page.getByTestId("onboarding-confirm").click();
  await expect(thread).toContainText(
    "You are live. Your customers get answers now, day or night.",
  );

  // 7. The owner's Home names the Work destination the way their labels do.
  await page.goto("/home");
  await expect(page.getByTestId("home-work-label")).toHaveText("Bookings");
});

test("a high-confidence guess is one tap, with no correction", async ({ page, request }) => {
  await stubRecords(page, recordsStore([]));
  await mockQueue(page, []);
  await page.route("**/api/tenants/me", (route) =>
    route.fulfill({
      json: {
        tenant_id: "00000000-0000-4000-8000-000000000001",
        slug: "bytefix",
        name: "Bytefix",
        brand: {},
        ordering: {
          mode: "orders",
          labels: { work: "Orders" },
        },
      },
    }),
  );

  const flow = await installFlow(page, nameStage());
  flow.onText = (text) => {
    expect(text).toBe("skip");
    return {
      reply: "No problem. Do you have a website or any documents?",
      state: sourceStage([
        { role: "assistant", content: "Before we start, what should I call you?" },
        { role: "user", content: "skip" },
        { role: "assistant", content: "No problem. Do you have a website or any documents?" },
      ]),
    };
  };
  flow.onSelection = () => sellingModeStage([{ role: "assistant", content: "How do customers buy from you?" }]);
  flow.onSellingMode = () =>
    storedModeStage("orders", [
      { role: "assistant", content: "Got it. Your assistant is ready to go live." },
    ]);

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  const composer = page.getByTestId("onboarding-composer");
  await composer.getByRole("textbox").fill("skip");
  await composer.getByRole("button", { name: "Send" }).click();
  await composer.getByRole("button", { name: "Skip for now" }).click();

  await page.getByTestId("selling-mode-confirm").click();

  // The confirm sends the inferred bundle, untouched.
  await expect.poll(() => flow.postedModes.length).toBe(1);
  expect(flow.postedModes[0]?.mode).toBe("orders");
  expect((flow.postedModes[0]?.capabilities as { sell: string[] }).sell).toEqual(["orders"]);

  await expect(page.getByTestId("selling-mode-card")).toHaveCount(0);

  // 32: the confirm screen shows the stored summary, and its [Edit] re-opens
  // the card over the stored config. The change view carries no inference
  // sentence any more - the authority is the summary above it.
  await expect(page.getByTestId("onboarding-selling-summary")).toContainText(ORDERS_SUMMARY);
  await page.getByTestId("onboarding-selling-edit").click();
  await expect(page.getByTestId("selling-mode-pick-orders")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByTestId("selling-mode-lead-time-30")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByTestId("selling-mode-summary")).toHaveCount(0);

  // The Home heading, from the same label map.
  await page.goto("/home");
  await expect(page.getByTestId("home-work-label")).toHaveText("Orders");
});
