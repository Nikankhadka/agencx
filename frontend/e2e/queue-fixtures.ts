/**
 * RF-14/D38: the Chats queue list endpoint answers with an envelope
 * (`{items, total, counts}`) and filters, searches, and pages on the server.
 *
 * Every spec that stubs the list must therefore (a) match the list URL with
 * its query string and (b) answer `filter`/`q`/`offset` the way the backend
 * does - a stub that returns the same rows for every filter would let the
 * client's server-driven behaviour pass vacuously, and a client that filtered
 * its own page would still look correct.
 *
 * The list URL is matched with a regex, not a glob: Playwright globs do not
 * match a query string, and the console layout fetches the bare
 * `/api/conversations` while the Chats page fetches it with `?filter=...`.
 * The regex covers both and excludes `/api/conversations/<id>`. Detail and
 * `/read` routes are registered after this one and win by Playwright's
 * last-registered-wins rule.
 */

import type { Page } from "@playwright/test";

export type FixtureRow = Record<string, unknown> & {
  id: string;
  needs_attention?: boolean;
  unread?: boolean;
  status?: string;
};

export const QUEUE_LIST_URL = /\/api\/conversations(\?.*)?$/;

export interface QueueCounts {
  all: number;
  needs_you: number;
  unread: number;
  human: number;
}

export interface QueueEnvelope {
  items: FixtureRow[];
  total: number;
  counts: QueueCounts;
}

/** Counts over a set of rows, mirroring the backend's D38 predicates. */
export function countsFor(rows: FixtureRow[]): QueueCounts {
  return {
    all: rows.length,
    needs_you: rows.filter((row) => row.needs_attention || row.status === "human").length,
    unread: rows.filter((row) => row.unread).length,
    human: rows.filter((row) => row.status === "human").length,
  };
}

/** The envelope for a set of rows, as one page holding all of them. */
export function listResponse(items: FixtureRow[]): QueueEnvelope {
  return { items, total: items.length, counts: countsFor(items) };
}

function applyFilter(rows: FixtureRow[], filter: string): FixtureRow[] {
  if (filter === "needs_you") return rows.filter((row) => row.needs_attention || row.status === "human");
  if (filter === "human") return rows.filter((row) => row.status === "human");
  if (filter === "unread") return rows.filter((row) => row.unread);
  return rows;
}

function matches(row: FixtureRow, q: string): boolean {
  if (!q) return true;
  const needle = q.toLowerCase();
  return (
    String(row.customer_ref ?? "").toLowerCase().includes(needle) ||
    row.id.replace(/-/g, "").includes(needle.replace(/^#/, ""))
  );
}

/**
 * Install a filter-, search-, and offset-aware list stub and return a probe of
 * every request's query string, so a test can assert what the client sent.
 * `limit` defaults to 50 when the request omits it. `rows` may be a getter so
 * a test can flip the dataset mid-flight (the four-second refresh case).
 */
export async function mockQueue(
  page: Page,
  rows: FixtureRow[] | (() => FixtureRow[]),
  onRequest?: () => void,
): Promise<string[]> {
  const urls: string[] = [];
  const current = typeof rows === "function" ? rows : () => rows;
  await page.route(QUEUE_LIST_URL, async (route) => {
    onRequest?.();
    const url = new URL(route.request().url());
    urls.push(url.search);
    const filter = url.searchParams.get("filter") ?? "all";
    const q = url.searchParams.get("q") ?? "";
    const offset = Number(url.searchParams.get("offset") ?? "0");
    const limit = Number(url.searchParams.get("limit") ?? "50");
    const searched = current().filter((row) => matches(row, q));
    const envelope: QueueEnvelope = {
      ...listResponse(searched),
      items: applyFilter(searched, filter).slice(offset, offset + limit),
    };
    await route.fulfill({ json: envelope });
  });
  return urls;
}
