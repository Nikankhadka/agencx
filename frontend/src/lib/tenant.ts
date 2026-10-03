import { createServerClient } from "@supabase/ssr";
import { cookies, headers } from "next/headers";
import { authCookieOptions } from "./auth-cookie";
import { serverPublicConfig } from "./public-config";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Server-side fetches (the RSC tenant lookup below) resolve the backend
 * through this base URL:
 * 1. `API_INTERNAL_URL` when set - the containerized dev stack uses it
 *    (`http://backend:8000`, F-3: localhost inside that container is itself),
 *    and Vercel's service binding supplies the private backend URL in
 *    production. No NEXT_ prefix, so it never gets inlined into browser
 *    bundles.
 * 2. The incoming request's own origin and deployment URL as fallbacks. This
 *    keeps a stale or unavailable deployment-level value from making a valid
 *    tenant look missing during a rollout.
 */
async function serverApiBaseUrls(): Promise<string[]> {
  const h = await headers();
  const proto = h.get("x-forwarded-proto")?.split(",")[0]?.trim() || "https";
  const forwardedHost = h.get("x-forwarded-host")?.split(",")[0]?.trim();
  const host = h.get("host")?.split(",")[0]?.trim();
  const deploymentUrl = h.get("x-vercel-deployment-url")?.split(",")[0]?.trim();

  return [...new Set([
    process.env.API_INTERNAL_URL,
    forwardedHost ? `${proto}://${forwardedHost}` : undefined,
    host ? `${proto}://${host}` : undefined,
    deploymentUrl ? `https://${deploymentUrl}` : undefined,
    API_URL,
  ].filter((base): base is string => Boolean(base)).map((base) => base.replace(/\/$/, "")))];
}

/**
 * Vercel may leave a stale service URL in API_INTERNAL_URL while routing the
 * public origin correctly. Try every known origin so a bad deployment-level
 * value cannot turn a valid tenant into the not-found page. All requests are
 * GETs, so retrying another origin is safe.
 */
async function fetchServerApi(path: string, init: RequestInit = {}): Promise<Response> {
  let notFound: Response | null = null;
  let lastError: unknown;

  for (const base of await serverApiBaseUrls()) {
    try {
      const res = await fetch(`${base}${path}`, { cache: "no-store", ...init });
      if (res.ok) return res;
      if (res.status === 404) {
        notFound ??= res;
        continue;
      }
      lastError = new Error(`server API request failed: ${res.status}`);
    } catch (error) {
      lastError = error;
    }
  }

  if (notFound) return notFound;
  throw lastError instanceof Error ? lastError : new Error("server API request failed");
}

export interface TenantResolution {
  id: string;
  name: string;
  status: string;
  brand: Record<string, unknown>;
  /** T-032: tenant-configured customer-surface block (config->'customer'):
   * optional greeting + starter_questions. Empty object when unconfigured,
   * absent entirely if a pre-T-032 backend answered this request. */
  customer?: Record<string, unknown>;
}

export interface StorefrontOffering {
  id: string;
  name: string;
  description: string;
  /**
   * The owner's own typed figure, in integer cents, or null when they
   * published no price. The page formats it; nothing here computes it.
   */
  price_cents: number | null;
  /** RF-4: display-only pricing wording, used when there is no fixed price. */
  pricing_wording?: string | null;
  category?: string | null;
  category_id?: string | null;
  categories?: Array<{ id: string; name: string; position: number; is_primary: boolean }>;
  media?: { type: string; provider: string; url: string; poster_url?: string | null } | null;
}

export interface StorefrontData {
  name: string;
  tagline: string | null;
  /** M-7 profile facts. Optional so a frontend deployed ahead of the backend
   * degrades to the no-facts state instead of throwing - deploy order between
   * the two should never matter. `contact` is never published. 20: `services`
   * is the owner's own overview, one entry per line they typed, and it may
   * carry their own rough price text - it is not the priced catalog. */
  business_type?: string | null;
  hours?: string | null;
  services?: string[];
  links: Record<string, string>;
  offerings: StorefrontOffering[];
  has_cover: boolean;
  cover_url?: string | null;
}

/**
 * Typed view over TenantResolution.customer with safe fallbacks. Accepts
 * undefined so a frontend deployed ahead of a pre-T-032 backend (missing the
 * `customer` field entirely) degrades to the no-greeting/no-chips state
 * instead of throwing - deploy order between the two should never matter.
 */
export function customerSurfaceConfig(customer: Record<string, unknown> | undefined): {
  greeting: string | null;
  starterQuestions: string[];
} {
  customer ??= {};
  const greeting =
    typeof customer["greeting"] === "string" && customer["greeting"].trim() !== ""
      ? customer["greeting"]
      : null;
  const raw = customer["starter_questions"];
  const starterQuestions = Array.isArray(raw)
    ? raw.filter((q): q is string => typeof q === "string" && q.trim() !== "").slice(0, 3)
    : [];
  return { greeting, starterQuestions };
}

/**
 * Server-side, unauthenticated fetch of GET /api/public/tenant/{slug} (T-005).
 * Returns null for an unknown slug (404) so callers can render the calm
 * not-found state instead of throwing.
 */
export async function resolveTenantBySlug(slug: string): Promise<TenantResolution | null> {
  const res = await fetchServerApi(`/api/public/tenant/${encodeURIComponent(slug)}`);
  if (res.status === 404) return null;
  return (await res.json()) as TenantResolution;
}

/** Public presentation content for a known active tenant. */
export async function resolveStorefrontBySlug(slug: string): Promise<StorefrontData> {
  const res = await fetchServerApi(`/api/public/tenant/${encodeURIComponent(slug)}/storefront`);
  if (!res.ok) throw new Error(`storefront resolve failed: ${res.status}`);
  return (await res.json()) as StorefrontData;
}

/**
 * RF-7: the signed-in viewer's own tenant slug, or null for an anonymous
 * visitor. Reads the Supabase session from the request cookies with the same
 * pinned cookie name and options `src/proxy.ts` uses (supabase-js derives the
 * name from the public URL, while the fetch may go through
 * `SUPABASE_INTERNAL_URL`), then calls the internal `GET /api/tenants/me` with
 * the session access token to learn which tenant the viewer owns.
 *
 * In a Server Component `setAll` cannot write cookies, so a refresh here is a
 * no-op and an expired session simply reads as anonymous - this is UX gating,
 * not enforcement (the backend verifies the bearer and RLS is the backstop).
 * Every failure resolves to null so the public page never errors on auth.
 */
export async function resolveViewerSlug(): Promise<string | null> {
  const { supabaseUrl, supabaseAnonKey } = serverPublicConfig();
  if (!supabaseUrl || !supabaseAnonKey) return null;

  const cookieName = `sb-${new URL(supabaseUrl).hostname.split(".")[0]}-auth-token`;
  const fetchUrl = process.env.SUPABASE_INTERNAL_URL || supabaseUrl;
  const cookieStore = await cookies();

  const supabase = createServerClient(fetchUrl, supabaseAnonKey, {
    cookieOptions: { name: cookieName, ...authCookieOptions() },
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll() {
        // Server Component: the response cannot set cookies. Explicit no-op.
      },
    },
  });

  const { data } = await supabase.auth.getSession();
  const accessToken = data.session?.access_token;
  if (!accessToken) return null;

  try {
    const res = await fetchServerApi("/api/tenants/me", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return null;
    const me = (await res.json()) as { slug?: unknown };
    return typeof me.slug === "string" ? me.slug : null;
  } catch {
    return null;
  }
}
