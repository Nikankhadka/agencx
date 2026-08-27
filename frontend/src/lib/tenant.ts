import { headers } from "next/headers";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Server-side fetches (the RSC tenant lookup below) resolve the backend
 * through this base URL:
 * 1. `API_INTERNAL_URL` when set - the containerized dev stack uses it
 *    (`http://backend:8000`, F-3: localhost inside that container is itself).
 *    No NEXT_ prefix, so it never gets inlined into browser bundles.
 * 2. The incoming request's own origin otherwise - on Vercel the edge rewrites
 *    `/api/*` to the backend service, so the same public origin the customer
 *    reached works from inside the frontend container too. The old service
 *    binding (`vercel.json`) was dropped because its injected internal URL is
 *    unreachable from the custom image (TLS to Vercel's internal CA fails).
 */
async function serverApiBaseUrl(): Promise<string> {
  const internal = process.env.API_INTERNAL_URL;
  if (internal) return internal;
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  const proto = h.get("x-forwarded-proto") ?? "https";
  if (host) return `${proto}://${host}`;
  return API_URL;
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
  const base = await serverApiBaseUrl();
  const res = await fetch(`${base}/api/public/tenant/${encodeURIComponent(slug)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`tenant resolve failed: ${res.status}`);
  return (await res.json()) as TenantResolution;
}
