import { expect, test, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";
import {
  draftRecord,
  MIDDLE_DOT,
  offeringCandidate,
  recordsStore,
  stubRecords,
} from "./knowledge-review-mocks";

/**
 * 29: source-first onboarding at the surface.
 *
 * Two runs of the same first two stages:
 *
 * 1. name -> Skip -> source -> attach a file -> the review opens -> save ->
 *    the beats the source left unanswered are asked -> confirm. The source
 *    endpoint is mocked (no provider needed) and answers state with
 *    candidates, exactly as the real one does after reading a menu.
 * 2. the no-source path: Skip on the name, Skip on the source, then the
 *    existing interview runs on the text path, unchanged.
 *
 * The onboarding server is a small state machine rather than a fixed reply, so
 * the client is driven by whatever stage it just moved to - and every request
 * is captured, because the point of the first two stages is which door the
 * client picks (the selection payload, not text; the source endpoint, not the
 * drafts batch).
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
}

interface Selection {
  beat: string;
  values: string[];
}

const NAME_SKIP: Chip = { label: "Skip", value: "skip", dashed: true, widget: null };

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

/** The state the backend answers with while the name beat is on screen. */
function nameStage(): ServerState {
  return view("owner_display_name", {
    prompt: "Before we start, what should I call you?",
    input: textInput({ chips: [NAME_SKIP] }),
    history: [{ role: "assistant", content: "Before we start, what should I call you?" }],
  });
}

/** ...and the source stage, which reuses the knowledge ask's own chip. */
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

interface Flow {
  /** What every read and turn answers with, until the flow moves it on. */
  state: ServerState;
  /** Selections the client posted, in order. */
  selections: Selection[];
  /** Typed turns the client streamed, in order. */
  texts: string[];
  streamCalls(): number;
  /** Multipart bodies the source endpoint received. */
  sourceUploads: { filename: string; hasDocType: boolean }[];
  draftsUploads(): number;
  confirmSlugs: string[];
  onSelection(selection: Selection): ServerState;
  onText(text: string): { reply: string; state: ServerState };
  onSourceUpload(filename: string): ServerState;
  onSave(): ServerState;
}

/**
 * The onboarding server as a state machine. Each route records what it was
 * asked, hands the decision to the test's handler, and answers with the state
 * the handler chose - so a client that reads the wrong stage after a turn
 * fails on the next assertion instead of passing on a canned reply.
 */
async function installFlow(
  page: Page,
  start: ServerState,
): Promise<Flow> {
  const selections: Selection[] = [];
  const texts: string[] = [];
  const sourceUploads: { filename: string; hasDocType: boolean }[] = [];
  const confirmSlugs: string[] = [];
  let streamCalls = 0;
  let draftsUploads = 0;

  const flow: Flow = {
    state: start,
    selections,
    texts,
    streamCalls: () => streamCalls,
    sourceUploads,
    draftsUploads: () => draftsUploads,
    confirmSlugs,
    onSelection: () => flow.state,
    onText: (text) => ({ reply: `Got it: ${text}`, state: flow.state }),
    onSourceUpload: () => flow.state,
    onSave: () => flow.state,
  };

  await page.route("**/api/onboarding/state", (route) =>
    route.fulfill({ json: flow.state }),
  );
  await page.route("**/api/onboarding/message", async (route) => {
    const body = route.request().postDataJSON() as { selection?: Selection };
    if (body.selection) {
      selections.push(body.selection);
      flow.state = flow.onSelection(body.selection);
    }
    await route.fulfill({ json: flow.state });
  });
  await page.route("**/api/onboarding/message/stream", async (route) => {
    streamCalls += 1;
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
  await page.route("**/api/onboarding/source", async (route) => {
    const post = route.request().postData() ?? "";
    const filename = post.match(/filename="([^"]+)"/)?.[1] ?? "";
    sourceUploads.push({ filename, hasDocType: post.includes('name="doc_type"') });
    flow.state = flow.onSourceUpload(filename);
    await route.fulfill({ json: flow.state });
  });
  // Neither of these belongs on the first two stages. Counting them - and
  // answering 500 so a stray call is loud - is what proves the client picked
  // the right door.
  await page.route("**/api/knowledge/drafts/upload", (route) => {
    draftsUploads += 1;
    return route.fulfill({ status: 500, json: {} });
  });
  await page.route("**/api/onboarding/knowledge/batch", async (route) => {
    flow.state = flow.onSave();
    await route.fulfill({
      json: { published: ["draft-1"], failed: [], offering_candidates: [] },
    });
  });
  await page.route("**/api/onboarding/confirm", async (route) => {
    confirmSlugs.push((route.request().postDataJSON() as { slug: string }).slug);
    await route.fulfill({ json: { tenant_id: "tenant-1", slug: "bytefix" } });
  });

  return flow;
}

const SHEET = { role: "dialog" as const, name: "Review your information" };

test("a source file opens the review, and the beats it left are asked after the save", async ({
  page,
  request,
}) => {
  const store = recordsStore([]);
  await stubRecords(page, store);
  const flow = await installFlow(page, nameStage());

  flow.onSelection = (selection) => {
    if (selection.beat === "owner_display_name") {
      expect(selection.values).toEqual(["skip"]);
      return sourceStage([
        { role: "assistant", content: "Before we start, what should I call you?" },
        { role: "user", content: "Skip" },
        { role: "assistant", content: "No problem. Do you have a website or any documents?" },
      ]);
    }
    // The source left the team question open, so it is asked before go-live.
    expect(selection).toEqual({ beat: "headcount", values: ["got a team"] });
    return view("confirm", {
      draft: { business_name: "Bytefix", services: ["Screen repair"], headcount: "got a team" },
      can_confirm: true,
      suggested_slug: "bytefix",
    });
  };
  flow.onSourceUpload = (filename) => {
    // The real endpoint stores the file as a reviewable draft; the review is
    // read back by the client from these two endpoints, not the POST body.
    store.records = [
      draftRecord({
        id: "draft-1",
        filename,
        sections: [{ heading: "What we offer", body: "Screen repair", kind: "other" }],
        offering_candidates: [offeringCandidate("Screen repair", "draft-1")],
      }),
    ];
    return view("services", {
      draft: { owner_display_name: "", business_name: "Bytefix", services: ["Screen repair"] },
      history: [
        { role: "assistant", content: "No problem. Do you have a website or any documents?" },
        { role: "user", content: filename },
        { role: "assistant", content: "Here's what I've got from your site." },
      ],
      can_confirm: false,
    });
  };
  // can_confirm stays false after the save: the source filled the details but
  // the team question is still open. The client must take that from the server.
  flow.onSave = () =>
    view("headcount", {
      prompt: "Is it just you, or do you work with a team?",
      draft: { business_name: "Bytefix", services: ["Screen repair"] },
      input: textInput({
        placeholder: "or type\u2026",
        chips: [
          { label: "Just me", value: "just me", dashed: false, widget: null },
          { label: "Got a team", value: "got a team", dashed: false, widget: null },
        ],
      }),
      can_confirm: false,
    });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  const thread = page.getByTestId("onboarding-thread");
  await expect(thread).toBeVisible();

  // 1. The name is the first stage and its Skip is a selection, not text.
  await page.getByTestId("onboarding-chip-skip").click();
  await expect.poll(() => flow.selections.length).toBe(1);
  expect(flow.streamCalls()).toBe(0);

  // 2. The source stage follows, with the same Skip and the attach affordance.
  const composer = page.getByTestId("onboarding-composer");
  await expect(composer.getByRole("textbox")).toHaveAttribute(
    "placeholder",
    /Paste a link or attach a file/,
  );
  await expect(composer.getByRole("button", { name: "Attach" })).toBeVisible();

  await page.getByTestId("onboarding-file-input").setInputFiles({
    name: "menu.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Screen repair, battery swap"),
  });

  // 3. The file went to the source endpoint (field `file`, no doc_type) and
  // never to the knowledge drafts batch.
  await expect.poll(() => flow.sourceUploads.length).toBe(1);
  expect(flow.sourceUploads[0]).toEqual({ filename: "menu.txt", hasDocType: false });
  expect(flow.draftsUploads()).toBe(0);
  await expect(
    thread.getByText(`menu.txt ${MIDDLE_DOT} ready`, { exact: true }),
  ).toBeVisible();

  // 4. The read-back from the server opens the review, priced and editable.
  const sheet = page.getByRole(SHEET.role, { name: SHEET.name });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByText("menu.txt", { exact: true })).toBeVisible();

  // 5. Save publishes, and the server - not the client - decides what follows.
  await sheet.getByTestId("onboarding-knowledge-save").click();
  await expect(page.getByTestId("onboarding-knowledge-save")).toHaveCount(0);
  await expect(page.getByTestId("onboarding-confirm")).toHaveCount(0);
  await expect(composer.getByRole("button", { name: "Got a team" })).toBeVisible();

  // 6. The beat the source left is answered, then confirm becomes available.
  await composer.getByRole("button", { name: "Got a team" }).click();
  await expect.poll(() => flow.selections.length).toBe(2);
  expect(flow.selections[1]).toEqual({ beat: "headcount", values: ["got a team"] });

  await expect(page.getByTestId("onboarding-confirm")).toBeVisible();
  await expect(page.getByTestId("onboarding-public-slug")).toHaveValue("bytefix");
  await page.getByTestId("onboarding-confirm").click();
  await expect(thread).toContainText(
    "You are live. Your customers get answers now, day or night.",
  );
  expect(flow.confirmSlugs).toEqual(["bytefix"]);
});

test("the no-source path keeps the existing interview unchanged", async ({
  page,
  request,
}) => {
  const store = recordsStore([]);
  await stubRecords(page, store);
  const flow = await installFlow(page, nameStage());

  flow.onSelection = (selection) => {
    if (selection.beat === "owner_display_name") {
      expect(selection.values).toEqual(["skip"]);
      return sourceStage([
        { role: "assistant", content: "Before we start, what should I call you?" },
        { role: "user", content: "Skip" },
        { role: "assistant", content: "No problem. Do you have a website or any documents?" },
      ]);
    }
    expect(selection).toEqual({ beat: "knowledge", values: ["skip"] });
    return view("business_name", {
      prompt: "What does the business go by?",
      input: textInput(),
      history: [
        { role: "assistant", content: "No problem. Do you have a website or any documents?" },
        { role: "user", content: "Skip for now" },
        { role: "assistant", content: "No problem. What does the business go by?" },
      ],
    });
  };
  flow.onText = (text) => {
    if (text === "Bytefix") {
      return {
        reply: "Got it. What days and hours are you open?",
        state: view("hours", {
          prompt: "What days and hours are you open?",
          input: textInput(),
          draft: { business_name: "Bytefix" },
          history: [{ role: "assistant", content: "What days and hours are you open?" }],
        }),
      };
    }
    return {
      reply: "Got it. Your assistant is ready to go live.",
      state: view("confirm", {
        draft: { business_name: "Bytefix", hours: "Weekdays 9 to 5" },
        can_confirm: true,
        suggested_slug: "bytefix",
      }),
    };
  };

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  const thread = page.getByTestId("onboarding-thread");
  await expect(thread).toBeVisible();
  const composer = page.getByTestId("onboarding-composer");

  // Name -> Skip, source -> Skip. Both are selections on the server's own
  // stage key, and neither touches the text path.
  await page.getByTestId("onboarding-chip-skip").click();
  await expect(composer.getByRole("textbox")).toHaveAttribute(
    "placeholder",
    /Paste a link or attach a file/,
  );
  await page.getByTestId("onboarding-chip-skip").click();

  await expect.poll(() => flow.selections.length).toBe(2);
  expect(flow.selections).toEqual([
    { beat: "owner_display_name", values: ["skip"] },
    { beat: "knowledge", values: ["skip"] },
  ]);
  expect(flow.streamCalls()).toBe(0);
  expect(flow.sourceUploads).toEqual([]);
  expect(flow.draftsUploads()).toBe(0);
  // Nothing was read, so there is nothing to review.
  await expect(page.getByRole(SHEET.role, { name: SHEET.name })).toHaveCount(0);

  // The interview resumes at the business name, on the text path it always
  // used - and the attach affordance is there too (29: every text stage).
  await expect(thread).toContainText("What does the business go by?");
  await expect(composer.getByRole("button", { name: "Attach" })).toBeVisible();
  await composer.getByRole("textbox").fill("Bytefix");
  await composer.getByRole("button", { name: "Send" }).click();
  await expect.poll(() => flow.texts).toEqual(["Bytefix"]);

  await expect(thread).toContainText("What days and hours are you open?");
  await composer.getByRole("textbox").fill("Weekdays 9 to 5");
  await composer.getByRole("button", { name: "Send" }).click();
  await expect.poll(() => flow.texts).toEqual(["Bytefix", "Weekdays 9 to 5"]);

  await expect(page.getByTestId("onboarding-confirm")).toBeVisible();
  await expect(page.getByTestId("onboarding-public-slug")).toHaveValue("bytefix");
});
