import { expect, test } from "@playwright/test";
import { DEMO_USERS, getAccessToken, loginAsTenantAdmin } from "./auth-helpers";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// In the containerized e2e runner the backend itself fetches this URL, and
// localhost:3000 inside that container is not the frontend (F-3) - compose
// points E2E_SITE_URL at the frontend service over the compose network.
const SITE_URL =
  process.env.E2E_SITE_URL ?? "http://localhost:3000/fixtures/example-business.html";

/**
 * O-3 US-1: an owner pastes their site into the onboarding thread and the
 * backend fetches it, ingests it as a `website` document, and reads back what
 * it found for confirmation.
 *
 * The target is a static fixture this app serves, so the fetch is real HTTP
 * against a page that is always up while the suite runs - no external network,
 * no third-party flake. It cannot be one of the app's own pages: those are
 * client-rendered, so their HTML carries no text an extractor could find.
 */
test("pasting a link reads the site and reads it back", async ({
  page,
  request,
}) => {
  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  const thread = page.getByTestId("onboarding-thread");
  await expect(thread).toBeVisible();

  // The thread is the tenant's stored history, so a re-run against the same
  // demo tenant starts with the previous run's read-back already in it. Count
  // what is there first and assert this turn ADDS one - "a read-back is
  // visible" would be satisfied by a stale line, and once there were two it
  // failed strict mode outright.
  const readBack = thread.getByText(
    /what I've got from your site|couldn't pin down the details/,
  );
  const before = await readBack.count();

  const composer = page.getByTestId("onboarding-composer");
  await composer.getByRole("textbox").fill(SITE_URL);
  await composer.getByRole("button", { name: "Send" }).click();

  // The stamp names the slow work while the fetch, ingest and extraction run
  // (the backend leads the URL turn with progress: reading_site for this).
  await expect(thread.getByText(/Reading your site/)).toBeVisible({
    timeout: 20_000,
  });

  // The read-back lands: either the fields the page stated, or the honest
  // "couldn't pin down the details" when it stated none.
  await expect(readBack).toHaveCount(before + 1, { timeout: 90_000 });
  await expect(readBack.last()).toBeVisible();
  // ...and the stamp it replaces is gone.
  await expect(thread.getByText(/Reading your site/)).toHaveCount(0);
  await expect(page.getByTestId("onboarding-error")).toHaveCount(0);

  // The site is now a ready `website` document, so the assistant can answer
  // from it - the read-back alone would not prove the ingest ran.
  const token = await getAccessToken(page);
  const docs = await request.get(`${BACKEND_URL}/api/knowledge`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(docs.ok()).toBe(true);
  const rows = (await docs.json()) as {
    filename: string;
    doc_type: string;
    status: string;
  }[];
  const site = rows.find((row) => row.filename === SITE_URL);
  expect(
    site,
    "the pasted URL should be stored as a website document",
  ).toBeTruthy();
  expect(site?.doc_type).toBe("website");
  expect(site?.status).toBe("ready");
});
