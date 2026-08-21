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

// ---------------------------------------------------------------------------
// Host helpers (Next.js 16 proxy.ts routes by Host header)
// ---------------------------------------------------------------------------

/** Reconstruct the tenant-admin host. */
export function tenantAdminHost(): string {
  return "app.localhost:3000";
}

/** Reconstruct the platform host. */
export function platformHost(): string {
  return "admin.localhost:3000";
}

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

/**
 * Log in through the tenant-admin login-in-chat (O-2): enter an email, fetch
 * the code the backend captured (dev-login-code), type the six digits.
 */
export async function loginInChat(
  page: Page,
  request: APIRequestContext,
  email: string
): Promise<void> {
  await page.goto("/login");
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByRole("button", { name: "Send" }).click();

  // The code phase must render before the captured code is fetched - the
  // login-code request has to land first.
  await page.getByLabel("Digit 1").waitFor({ timeout: 10_000 });
  const codeResp = await request.get(
    `${BACKEND_URL}/api/auth/dev-login-code?email=${encodeURIComponent(email)}`
  );
  if (!codeResp.ok()) {
    throw new Error(`dev-login-code failed: ${codeResp.status()}`);
  }
  const { code } = (await codeResp.json()) as { code: string };
  for (let i = 0; i < 6; i++) {
    await page.getByLabel(`Digit ${i + 1}`).fill(code[i]);
  }
  await page.waitForURL("**/onboarding");
}

/**
 * Log in as a tenant-admin user (login-in-chat), then verify the post-login
 * redirect into the admin console shell at /onboarding.
 */
export async function loginAsTenantAdmin(
  page: Page,
  request: APIRequestContext,
  user: DemoUser
): Promise<void> {
  await loginInChat(page, request, user.email);
}

/**
 * Log in as a platform-admin user, then verify redirect to the admin console
 * root ("/") which shows the Tenants page.
 */
export async function loginAsPlatformAdmin(page: Page, user: DemoUser): Promise<void> {
  await page.goto("/login");
  await submitLoginForm(page, user.email, user.password);
  // T-033: on success the page redirects to "/" which is the Tenants page.
  await page.getByRole("heading", { name: "Tenants" }).waitFor({ timeout: 10_000 });
}
