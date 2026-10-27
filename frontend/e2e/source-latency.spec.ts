import { appendFileSync } from "node:fs";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { getAccessToken, loginInChat } from "./auth-helpers";

/**
 * Opt-in measurement of the whole owner path, from submitting a web source to
 * the review sheet being on screen. Never runs in a normal e2e run or in CI:
 * every test here is skipped unless `SOURCE_LATENCY` is set.
 *
 *   SOURCE_LATENCY=1 SOURCE_FLOW=new SOURCE_RUNS=3 \
 *   SOURCE_URL=https://www.thegrounds.com.au/ \
 *   SOURCE_LATENCY_OUT=/abs/path/rows.jsonl \
 *   npx playwright test e2e/source-latency.spec.ts --project=chromium
 *
 * `SOURCE_FLOW=old` drives the pre-ticket interview (name, business name, type,
 * headcount, hours, services, voice, contact, ABN) and only then the website
 * ask; `new` drives the source-first flow (name Skip, then the source stage).
 * Both submit the same URL through the same composer into the same review
 * sheet, so the two numbers are one owner action on two implementations.
 *
 * Measurement is in-page and read-only: a capture-phase click listener stamps
 * `performance.now()` at the start of the Send button's handler, and a
 * requestAnimationFrame loop stamps the first progress copy and the first
 * offering row painted inside the review sheet. No app code is touched.
 *
 * Evidence: docs/agencx/evidence/onboarding-source-2026-10/e2e-side-by-side.md
 */

const ENABLED = Boolean(process.env.SOURCE_LATENCY);
const FLOW = process.env.SOURCE_FLOW === "old" ? "old" : "new";
const RUNS = Number(process.env.SOURCE_RUNS ?? 3);
const SITE_URL = process.env.SOURCE_URL ?? "https://www.thegrounds.com.au/";
const OUT = process.env.SOURCE_LATENCY_OUT ?? "";
const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface LatencyProbe {
  t0: number | null;
  tFeedback: number | null;
  tDialog: number | null;
  tReview: number | null;
  reviewAnchor: "offering" | "empty" | null;
  retainedCount: number;
  pricesMissing: boolean;
}

function record(row: Record<string, unknown>): void {
  if (!OUT) return;
  appendFileSync(OUT, `${JSON.stringify(row)}\n`);
}

/** Install the in-page probe. Must run on the onboarding page before the submit. */
async function installProbe(page: Page): Promise<void> {
  await page.evaluate(() => {
    const probe = {
      t0: null as number | null,
      tFeedback: null as number | null,
      tDialog: null as number | null,
      tReview: null as number | null,
      reviewAnchor: null as "offering" | "empty" | null,
      retainedCount: -1,
      pricesMissing: false,
    };
    (window as unknown as { __lat: typeof probe }).__lat = probe;
    (window as unknown as { __arm: boolean }).__arm = false;

    // Capture phase: runs before React's own submit handler.
    document.addEventListener(
      "click",
      (event) => {
        const armed = (window as unknown as { __arm: boolean }).__arm;
        if (!armed || probe.t0 !== null) return;
        const button = (event.target as Element | null)?.closest?.("button");
        const label = (button?.getAttribute("aria-label") ?? "").trim();
        const text = (button?.textContent ?? "").trim();
        if (button && (label === "Send" || text === "Send")) {
          probe.t0 = performance.now();
        }
      },
      true,
    );

    const tick = () => {
      if (probe.t0 !== null) {
        if (probe.tFeedback === null) {
          const stamp = document.querySelector(
            '[data-testid="onboarding-thread"] p.text-proc',
          );
          if (stamp && /Reading your site|Finding your services|Waiting for your review/.test(stamp.textContent ?? "")) {
            probe.tFeedback = performance.now();
          }
        }
        const dialog = document.querySelector('[role="dialog"]');
        if (dialog) {
          // The Sheet stays mounted while closed (it slides off-screen), and
          // renders its own header there - the footer button only exists while
          // it is actually open.
          const open = dialog.querySelector('[data-testid="onboarding-knowledge-save"]');
          if (probe.tDialog === null && open) probe.tDialog = performance.now();
          if (probe.tReview === null) {
            // The offerings section is the one whose own text says how many
            // offerings it retained. Its first row is an editable row's name
            // field or a read-only row's heading; when the extraction found
            // nothing, the section's "No offerings yet." line is the same
            // paint and is recorded as the empty anchor.
            const section = Array.from(dialog.querySelectorAll("section")).find((node) =>
              /retained offering/.test(node.textContent ?? ""),
            );
            const row =
              section?.querySelector('input[aria-label$=" name"], h4') ??
              Array.from(section?.querySelectorAll("p") ?? []).find(
                (node) => (node.textContent ?? "").trim() === "No offerings yet.",
              );
            if (row && (row as HTMLElement).getClientRects().length > 0) {
              probe.tReview = performance.now();
              probe.reviewAnchor = row.tagName === "P" ? "empty" : "offering";
              const countText = Array.from(section?.querySelectorAll("p") ?? [])
                .map((node) => node.textContent ?? "")
                .join(" ");
              probe.retainedCount = Number(
                countText.match(/(\d+)\s+retained offering/)?.[1] ?? -1,
              );
              probe.pricesMissing = Boolean(
                dialog.querySelector('[data-testid="review-missing-prices"]'),
              );
            }
          }
        }
        if (probe.tReview !== null) return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

async function readProbe(page: Page): Promise<LatencyProbe> {
  return page.evaluate(() => {
    const probe = (window as unknown as { __lat: LatencyProbe }).__lat;
    return {
      t0: probe.t0,
      tFeedback: probe.tFeedback,
      tDialog: probe.tDialog,
      tReview: probe.tReview,
      reviewAnchor: probe.reviewAnchor,
      retainedCount: probe.retainedCount,
      pricesMissing: Boolean(probe.pricesMissing),
    };
  });
}

async function armAndSubmit(page: Page, url: string): Promise<void> {
  const composer = page.getByTestId("onboarding-composer");
  await composer.getByRole("textbox").fill(url);
  await page.evaluate(() => {
    (window as unknown as { __arm: boolean }).__arm = true;
  });
  await composer.getByRole("button", { name: "Send" }).click();
}

async function stageOf(request: APIRequestContext, token: string): Promise<string> {
  const resp = await request.get(`${BACKEND_URL}/api/onboarding/state`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resp.ok()).toBe(true);
  return ((await resp.json()) as { stage: string }).stage;
}

/**
 * Answer one beat and wait for its request to settle. A typed answer streams
 * from `/api/onboarding/message/stream`; a chip posts to `/api/onboarding/message`.
 */
async function answer(
  page: Page,
  action: "text" | "chip",
  value: string,
): Promise<void> {
  const composer = page.getByTestId("onboarding-composer");
  const settled = page.waitForResponse(
    (response) =>
      response.url().includes("/api/onboarding/message") &&
      response.request().method() === "POST",
    { timeout: 120_000 },
  );
  if (action === "chip") {
    await composer.getByRole("button", { name: value, exact: true }).click();
  } else {
    await composer.getByRole("textbox").fill(value);
    await composer.getByRole("button", { name: "Send" }).click();
  }
  await settled;
}

/**
 * Answer a beat and wait for the interview to leave it. A typed answer can come
 * back as the read-back question ("I have X. Is that right?") with Yes/No chips
 * while the stage stays put, so that confirmation is part of the beat.
 */
async function answerAndAdvance(
  page: Page,
  request: APIRequestContext,
  token: string,
  action: "text" | "chip",
  value: string,
  stage: string,
): Promise<void> {
  await answer(page, action, value);
  for (let round = 0; round < 3; round++) {
    await expect
      .poll(
        async () => {
          if ((await stageOf(request, token)) !== stage) return "moved";
          const yes = page
            .getByTestId("onboarding-composer")
            .getByRole("button", { name: "Yes", exact: true });
          return (await yes.count()) > 0 ? "confirm" : "wait";
        },
        { timeout: 120_000, intervals: [250] },
      )
      .not.toBe("wait");
    if ((await stageOf(request, token)) !== stage) return;
    await answer(page, "chip", "Yes");
  }
  throw new Error(`beat ${stage} did not advance after confirming its read-back`);
}

/** The pre-ticket interview, driven to the website ask. */
async function driveOldInterview(
  page: Page,
  request: APIRequestContext,
  token: string,
  ownerEmail: string,
): Promise<void> {
  const beats: { stage: string; action: "text" | "chip"; value: string }[] = [
    { stage: "owner_display_name", action: "text", value: "Perf Owner" },
    { stage: "business_name", action: "text", value: "Perf Grounds Cafe" },
    { stage: "business_type", action: "text", value: "cafe" },
    { stage: "headcount", action: "chip", value: "Just me" },
    { stage: "hours", action: "text", value: "7am to 3pm every day" },
    { stage: "services", action: "text", value: "coffee and breakfast, $4 to $20" },
    { stage: "customer_voice_preset", action: "chip", value: "Warm and casual" },
    { stage: "contact", action: "chip", value: ownerEmail },
    { stage: "abn", action: "chip", value: "No" },
  ];
  for (const beat of beats) {
    await expect
      .poll(() => stageOf(request, token), { timeout: 120_000 })
      .toBe(beat.stage);
    await answerAndAdvance(page, request, token, beat.action, beat.value, beat.stage);
  }
  // Answering ABN "No" completes the profile, so the completion reply opens the
  // website ask.
  await expect.poll(() => stageOf(request, token), { timeout: 120_000 }).toBe("knowledge");
}

for (let run = 1; run <= RUNS; run++) {
  test(`source latency ${FLOW} run ${run}`, async ({ page, request }) => {
    test.skip(!ENABLED, "opt-in measurement: set SOURCE_LATENCY=1");
    test.setTimeout(600_000);

    const email = `perf-${FLOW}-${run}-${Date.now()}@perf.dev`;
    const row: Record<string, unknown> = {
      flow: FLOW,
      run,
      url: SITE_URL,
      email,
      ok: false,
      started_at: new Date().toISOString(),
    };

    try {
      await loginInChat(page, request, email);
      const thread = page.getByTestId("onboarding-thread");
      await expect(thread).toBeVisible();
      const composer = page.getByTestId("onboarding-composer");
      await expect(composer).toBeVisible();
      const token = await getAccessToken(page);

      if (FLOW === "new") {
        await composer.getByTestId("onboarding-chip-skip").click();
        await expect(composer.getByRole("textbox")).toHaveAttribute(
          "placeholder",
          /Paste a link or attach a file/,
          { timeout: 30_000 },
        );
      } else {
        await driveOldInterview(page, request, token, email);
        await expect(composer.getByRole("textbox")).toHaveAttribute(
          "placeholder",
          /Paste a link or attach a file/,
          { timeout: 30_000 },
        );
      }

      await installProbe(page);
      row.submitted_at = new Date().toISOString();
      await armAndSubmit(page, SITE_URL);
      // The stamp comes from the button's own handler; if it did not fire the
      // whole run is unmeasurable, so fail fast rather than wait out the review.
      await expect
        .poll(async () => (await readProbe(page)).t0, { timeout: 15_000, intervals: [100] })
        .not.toBeNull();

      await expect
        .poll(async () => (await readProbe(page)).tReview, {
          timeout: 300_000,
          intervals: [200],
        })
        .not.toBeNull();
      const probe = await readProbe(page);

      row.t0 = probe.t0;
      row.t_feedback_ms = probe.tFeedback;
      row.t_dialog_ms = probe.tDialog;
      row.t_review_ms = probe.tReview;
      row.review_anchor = probe.reviewAnchor;
      row.retained_count = probe.retainedCount;
      row.prices_missing = probe.pricesMissing;
      row.ok = true;
      record(row);
    } catch (error) {
      row.error = error instanceof Error ? error.message.slice(0, 400) : String(error);
      record(row);
      throw error;
    }
  });
}
