/**
 * Shared E2E auth helpers for Wren.
 *
 * Centralises demo credentials and login interaction logic so individual spec
 * files don't duplicate selectors and input sequences.
 */

import type { APIRequestContext, Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Demo identities (from backend/seeds/seed_demo.py)
// ---------------------------------------------------------------------------

export interface DemoUser {
  email: string;
  password: string;
  surface: "tenant-admin" | "platform";
}

export const DEMO_USERS: DemoUser[] = [
  {
    email: "owner@bytefix.dev",
    password: "wren-demo",
    surface: "tenant-admin",
  },
  {
    email: "owner@lumident.dev",
    password: "wren-demo",
    surface: "tenant-admin",
  },
  {
    email: "founder@wren.dev",
    password: "wren-demo",
    surface: "platform",
  },
];

// Since D22 every surface is one origin - the tenant is a path (`/{slug}`)
// and the platform lives under `/admin`. Specs use the config baseURL and
// relative paths; there are no per-surface hosts to reconstruct.

// GoTrue is the OTP issuer now (auth migration) and mails through Mailpit
// (docker-compose.yml's `auth` service). No env var to override this: the
// same Makefile socat mirror that forwards 3000/8000/54321 onto the e2e
// runner's own loopback (F-3) forwards 8025 too, so this default reaches
// Mailpit identically from a host run or the containerized runner.
const MAILPIT_URL = "http://localhost:8025";

// ---------------------------------------------------------------------------
// Login interaction helpers
// ---------------------------------------------------------------------------

/** Fill and submit the login form (platform surface; email + password). */
export async function submitLoginForm(
  page: Page,
  email: string,
  password: string
): Promise<void> {
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
}

interface MailpitMessage {
  Created: string;
  Snippet: string;
}

/**
 * Poll Mailpit for the OTP GoTrue just mailed to `email` and return its six
 * digits. "Newest matching message" is correct only with a cutoff: the send
 * this helper is waiting on happened moments ago, but specs share the demo
 * users, so a *previous* login's mail for the same address can still be the
 * newest when this poll starts (parallel workers or a repeated spec). Ignore
 * anything older than the poll's own start (with a small grace for delivery
 * lag), so the code returned is always this attempt's. Polls rather than
 * fetching once because delivery (real SMTP, even to a local relay) is not
 * instant.
 */
export async function fetchOtpCode(request: APIRequestContext, email: string): Promise<string> {
  const startedAt = Date.now() - 2000;
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    const resp = await request.get(
      `${MAILPIT_URL}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`
    );
    if (resp.ok()) {
      const { messages } = (await resp.json()) as { messages: MailpitMessage[] };
      const newest = messages
        .filter((m) => new Date(m.Created).getTime() >= startedAt)
        .reduce<MailpitMessage | null>(
          (latest, m) => (!latest || m.Created > latest.Created ? m : latest),
          null
        );
      const code = newest?.Snippet.match(/\b(\d{6})\b/)?.[1];
      if (code) return code;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`no OTP code arrived in Mailpit for ${email} within 10s`);
}

/**
 * Log in through the tenant-admin login-in-chat (O-2): enter an email, read
 * the six-digit code GoTrue mails via Mailpit, type it back.
 *
 * Retries in place on a stale code: the specs share the demo users, so two
 * workers can be logging in as the same owner at once, and GoTrue keeps only
 * one OTP per address - a later send invalidates the code this attempt just
 * fetched. The login page's own "Wrong email?" escape re-arms the email phase
 * with the address still in the pill, so a retry goes through real UI rather
 * than reloading (a reload could race the session redirect).
 *
 * The landing after a successful login is either /onboarding (a tenant that
 * has not gone live yet) or /home (an already-onboarded tenant - the
 * onboarding page redirects there immediately), so both are accepted as
 * success.
 */
export async function loginInChat(
  page: Page,
  request: APIRequestContext,
  email: string
): Promise<void> {
  await page.goto("/login");
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByRole("button", { name: "Send" }).click();
  await page.getByLabel("Digit 1").waitFor({ timeout: 10_000 });

  for (let attempt = 0; attempt < 3; attempt++) {
    const code = await fetchOtpCode(request, email);
    for (let i = 0; i < 6; i++) {
      await page.getByLabel(`Digit ${i + 1}`).fill(code[i]);
    }
    const landed = await page
      .waitForURL(/\/(onboarding|home)/, { timeout: 10_000 })
      .then(() => true)
      .catch(() => false);
    if (landed) return;
    await page.getByRole("button", { name: "Wrong email?" }).click();
    await page.getByRole("button", { name: "Send" }).click();
    await page.getByLabel("Digit 1").waitFor({ timeout: 10_000 });
  }
  await page.waitForURL(/\/(onboarding|home)/);
}

/**
 * Log in as a tenant-admin user (login-in-chat), then verify the post-login
 * redirect into the admin console shell (onboarding for a tenant that has not
 * gone live, home for one already onboarded).
 */
export async function loginAsTenantAdmin(
  page: Page,
  request: APIRequestContext,
  user: DemoUser
): Promise<void> {
  await loginInChat(page, request, user.email);
}

/**
 * Log in as a platform-admin user, then verify redirect to the platform console
 * root ("/admin") which shows the Tenants page.
 */
export async function loginAsPlatformAdmin(page: Page, user: DemoUser): Promise<void> {
  await page.goto("/admin/login");
  await submitLoginForm(page, user.email, user.password);
  // T-033: on success the page redirects to "/admin", the Tenants page.
  await page.getByRole("heading", { name: "Tenants" }).waitFor({ timeout: 10_000 });
}

// ---------------------------------------------------------------------------
// Raw bearer token (for specs that hit the backend directly, bypassing the
// app's own fetch wrapper)
// ---------------------------------------------------------------------------

// Matches how src/proxy.ts and supabase-js itself derive the session cookie's
// name from the Supabase URL - see proxy.ts for the full rationale.
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://localhost:54321";
const SESSION_COOKIE_NAME = `sb-${new URL(SUPABASE_URL).hostname.split(".")[0]}-auth-token`;

/**
 * The signed-in session's access token, read out of the cookie
 * `@supabase/ssr` writes - the same source `lib/api.ts`'s `getAuthHeaders`
 * reads via `getSupabase().auth.getSession()`. There is no longer a
 * localStorage session to read directly (the auth migration moved it to this
 * cookie), and the cookie is the one place outside the app's own bundled
 * supabase-js instance that actually holds the token.
 *
 * ponytail: assumes one unchunked cookie (`@supabase/ssr` splits a session
 * across `.0`/`.1`/... cookies past ~3180 bytes) - true for every session
 * observed in this suite (~2.7KB). A session that grows past the chunking
 * threshold needs this to reassemble the chunks first.
 */
export async function getAccessToken(page: Page): Promise<string> {
  const cookies = await page.context().cookies();
  const session = cookies.find((c) => c.name === SESSION_COOKIE_NAME);
  if (!session) {
    throw new Error(`no ${SESSION_COOKIE_NAME} cookie found - is this page signed in?`);
  }
  const raw = session.value.startsWith("base64-") ? session.value.slice(7) : session.value;
  const { access_token: accessToken } = JSON.parse(
    Buffer.from(raw, "base64url").toString("utf8")
  ) as { access_token: string };
  return accessToken;
}
