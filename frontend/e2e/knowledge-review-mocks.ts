/**
 * W-11c Phase 5: shared fully-mocked fixtures and route stubs for the
 * knowledge-review e2e specs (desktop + mobile). Every route here is
 * installed BEFORE loginAsTenantAdmin - the onboarding page's mount does
 * Promise.all over /api/onboarding/state and /api/knowledge/records, so the
 * stubs must exist before the first navigation.
 *
 * The route handlers are stateful: a records store is mutated by uploads and
 * deletes, so the page's own refetches see a consistent world, and each stub
 * exposes counters the tests assert on (in-flight uploads, DELETE calls,
 * served record bodies).
 */
import type { Page } from "@playwright/test";

export interface MockOffering {
  candidate_id?: string;
  name: string;
  description?: string;
  price_cents?: number | null;
  sources?: ("owner" | "document")[];
  supporting_document_ids?: string[];
  support_state?: "supported" | "orphaned";
}

export interface MockKnowledgeRecord {
  id: string;
  filename: string;
  doc_type: string;
  status: string;
  error: string | null;
  sections: { heading: string; body: string; kind?: string }[];
  offering_candidates: MockOffering[];
  extraction_status: "full" | "partial" | "failed" | "pending";
  failure_stage?: "structure" | "extract" | "embed" | null;
  failure_retryable?: boolean | null;
  failed_at?: string | null;
}

export interface MockBatchFailure {
  document_id: string;
  error: string;
}

export interface MockBatchResponse {
  published: string[];
  failed: MockBatchFailure[];
  offering_candidates: MockOffering[];
}

/** The middle dot in thread stamps ("notes.txt · ready"), U+00B7. */
export const MIDDLE_DOT = "\u00b7";

/** A bare text beat, like onboarding-transport.spec.ts uses. */
export function textInputSpec(placeholder = "") {
  return {
    kind: "text",
    placeholder,
    chips: [],
    mask: null,
    cta_label: null,
    prefix: null,
    suggest_owner_email: false,
  };
}

/** The canonical mid-interview state the other onboarding specs stub. */
export function onboardingState(overrides: Record<string, unknown> = {}) {
  return {
    stage: "services",
    prompt: "What do you offer?",
    draft: { name: "Ronin", business_name: "Test Repairs" },
    completed: false,
    history: [{ role: "assistant", content: "What do you offer?" }],
    input: textInputSpec(),
    can_confirm: false,
    suggested_slug: "test-repairs",
    paused_beat: null,
    missing_required: [],
    ...overrides,
  };
}

export async function stubOnboardingState(
  page: Page,
  overrides: Record<string, unknown> = {},
): Promise<void> {
  await page.route("**/api/onboarding/state", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(onboardingState(overrides)),
    }),
  );
}

/** The canonical draft record, after onboarding-go-live.spec.ts, plus the
 *  extraction_status the combined sheet renders from. */
export function draftRecord(
  overrides: Partial<MockKnowledgeRecord> = {},
): MockKnowledgeRecord {
  return {
    id: "draft-1",
    filename: "notes.txt",
    doc_type: "other",
    status: "draft",
    error: null,
    sections: [{ heading: "Hours", body: "9 to 5, Monday to Friday", kind: "hours" }],
    offering_candidates: [],
    extraction_status: "full",
    ...overrides,
  };
}

/** A document-sourced offering candidate, tied to the record that carries it. */
export function offeringCandidate(
  name: string,
  documentId: string,
  overrides: Partial<MockOffering> = {},
): MockOffering {
  return {
    name,
    description: "",
    price_cents: null,
    sources: ["document"],
    supporting_document_ids: [documentId],
    ...overrides,
  };
}

/** The server's records list, shared by the records/upload/delete stubs.
 *  `deletedIds` is the one ledger wherever a row disappears, so a replacement
 *  performed by the URL endpoint is visible beside a plain DELETE. */
export interface RecordsStore {
  records: MockKnowledgeRecord[];
  deletedIds: string[];
}

export function recordsStore(initial: MockKnowledgeRecord[]): RecordsStore {
  return { records: [...initial], deletedIds: [] };
}

export interface RecordsStub {
  getCount(): number;
  deleteCount(): number;
  deletedIds(): string[];
  /** The JSON body of the most recent GET /api/knowledge/records response. */
  lastGetBody(): string;
}

/** GET /api/knowledge/records serves the store; DELETE /api/knowledge/records
 *  /{id} removes one row, returns 204, and is counted. */
export async function stubRecords(page: Page, store: RecordsStore): Promise<RecordsStub> {
  let getCount = 0;
  let deleteCount = 0;
  let lastGetBody = "[]";
  await page.route("**/api/knowledge/records", (route) => {
    getCount += 1;
    lastGetBody = JSON.stringify(store.records);
    return route.fulfill({ contentType: "application/json", body: lastGetBody });
  });
  await page.route("**/api/knowledge/records/*", (route) => {
    deleteCount += 1;
    const id = route.request().url().match(/\/records\/([^/]+)$/)?.[1] ?? "";
    store.deletedIds.push(decodeURIComponent(id));
    store.records = store.records.filter((record) => record.id !== id);
    return route.fulfill({ status: 204, body: "" });
  });
  return {
    getCount: () => getCount,
    deleteCount: () => deleteCount,
    deletedIds: () => [...store.deletedIds],
    lastGetBody: () => lastGetBody,
  };
}

export interface SourceUrlCall {
  url: string;
  replace_document_id: string | null;
}

export interface SourceUrlStub {
  /** Every posted body, in order - a cancelled editor records none. */
  calls(): SourceUrlCall[];
}

export interface SourceUrlOptions {
  /** The document the site reader would produce for this request. */
  recordFor: (url: string, replaceDocumentId: string | null) => MockKnowledgeRecord;
  /** Overrides for the state the endpoint answers beside the document. */
  state?: Record<string, unknown>;
}

/**
 * 31: POST /api/onboarding/source/url, fulfilled from the store so the E2E
 * never crawls a real site. A replacement with a different id removes the old
 * row and records it on the store's deleted ledger; a re-read of the same
 * address updates that row in place. The posted body is kept for assertions.
 */
export async function stubSourceUrl(
  page: Page,
  store: RecordsStore,
  options: SourceUrlOptions,
): Promise<SourceUrlStub> {
  const calls: SourceUrlCall[] = [];
  await page.route("**/api/onboarding/source/url", (route) => {
    let body: { url?: string; replace_document_id?: string | null } = {};
    try {
      body = (route.request().postDataJSON() ?? {}) as typeof body;
    } catch {
      body = {};
    }
    const url = body.url ?? "";
    const replaceDocumentId = body.replace_document_id ?? null;
    calls.push({ url, replace_document_id: replaceDocumentId });
    const record = options.recordFor(url, replaceDocumentId);
    if (replaceDocumentId !== null && replaceDocumentId !== record.id) {
      store.records = store.records.filter((item) => item.id !== replaceDocumentId);
      store.deletedIds.push(replaceDocumentId);
      store.records = [...store.records, record];
    } else {
      const index = store.records.findIndex((item) => item.id === record.id);
      if (index >= 0) store.records = store.records.map((item, position) => (position === index ? record : item));
      else store.records = [...store.records, record];
    }
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ state: onboardingState(options.state), document: record }),
    });
  });
  return { calls: () => [...calls] };
}

export interface UploadStub {
  /** The most uploads the page ever had in flight at once. */
  maxInFlight(): number;
  /** How many upload requests have completed (fulfilled or failed). */
  settled(): number;
  calls(): number;
}

export interface UploadOptions {
  delayMs?: number;
  /** Build the record a successful upload stores, from the uploaded filename. */
  recordFor: (filename: string) => MockKnowledgeRecord;
  /** Every upload answers 500 instead of storing a record. */
  failAll?: boolean;
}

/** POST /api/knowledge/drafts/upload: counts in-flight uploads (the page's
 *  runBounded cap is what the test asserts against), delays, then either
 *  stores the recordFor(filename) result and answers 201, or answers 500. */
export async function stubUpload(
  page: Page,
  store: RecordsStore,
  options: UploadOptions,
): Promise<UploadStub> {
  let inFlight = 0;
  let maxInFlight = 0;
  let settled = 0;
  let calls = 0;
  await page.route("**/api/knowledge/drafts/upload", async (route) => {
    calls += 1;
    inFlight += 1;
    maxInFlight = Math.max(maxInFlight, inFlight);
    await new Promise((resolve) => setTimeout(resolve, options.delayMs ?? 300));
    inFlight -= 1;
    settled += 1;
    if (options.failAll) {
      return route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          type: "about:blank",
          title: "Internal Server Error",
          status: 500,
          detail: "Upload failed",
          code: "upstream_error",
        }),
      });
    }
    const filename =
      route.request().postData()?.match(/filename="([^"]+)"/)?.[1] ?? "upload.txt";
    const record = options.recordFor(filename);
    store.records = [...store.records, record];
    return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(record) });
  });
  return {
    maxInFlight: () => maxInFlight,
    settled: () => settled,
    calls: () => calls,
  };
}

export interface BatchStub {
  setResponse(next: MockBatchResponse): void;
  calls(): number;
}

/** PUT /api/onboarding/knowledge/batch answers the current response; the
 *  tests swap it between saves to move from a partial failure to success.
 *  Serving a response also moves the store's records to match the backend
 *  (controller.py save_onboarding_knowledge_batch): published documents leave
 *  the drafts, failed documents park as status "failed" so the refetched
 *  record carries the failure the sheet renders. */
export async function stubBatch(
  page: Page,
  store: RecordsStore,
  response: MockBatchResponse,
): Promise<BatchStub> {
  let current = response;
  let calls = 0;
  await page.route("**/api/onboarding/knowledge/batch", (route) => {
    calls += 1;
    const published = new Set(current.published);
    const failed = new Set(current.failed.map((failure) => failure.document_id));
    store.records = store.records.map((record) => {
      if (failed.has(record.id)) return { ...record, status: "failed" };
      if (published.has(record.id)) return { ...record, status: "published" };
      return record;
    });
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(current),
    });
  });
  return { setResponse: (next) => { current = next; }, calls: () => calls };
}

/** setInputFiles payloads for the composer's file input - one text file per
 *  name, so a test can pick N distinct files without touching disk. */
export function uploadFilePayloads(names: string[]): { name: string; mimeType: string; buffer: Buffer }[] {
  return names.map((name) => ({
    name,
    mimeType: "text/plain",
    buffer: Buffer.from(`Contents of ${name}`),
  }));
}