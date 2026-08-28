import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { authCookieOptions } from "@/lib/auth-cookie";
import { serverPublicConfig } from "@/lib/public-config";

/**
 * Server-side session guard (auth migration, closing G2.2's client-side-only
 * route protection). Next 16 renamed `middleware` to `proxy` - this file has
 * to live at `src/proxy.ts` (next to `src/app`), not the repo root.
 *
 * This is UX, not the enforcement boundary: the backend verifies every bearer
 * token itself (shared/auth.py) and RLS is the real backstop underneath that
 * (database.md sections 2-3), matching the defense-in-depth posture
 * industry-standard-gap.md's G2.2 write-up calls for after CVE-2025-29927
 * proved proxy-only auth is bypassable. What this buys is a server-rendered
 * redirect instead of a client-side flash of a page the owner has no session
 * for.
 *
 * The matcher is a positive list on purpose, never a catch-all: the customer
 * surface (`/[slug]`) is anonymous by product design (database.md section
 * 297) and must never see this file run, and `/` (the login chat's apex) and
 * static assets are likewise untouched.
 */
export const config = {
  matcher: [
    "/(home|chats|business|conversations|escalations|pricing|knowledge|dashboards|onboarding)/:path*",
    "/login",
    "/admin/:path*",
  ],
};

const CONSOLE_PREFIXES = [
  "/home",
  "/chats",
  "/business",
  "/conversations",
  "/escalations",
  "/pricing",
  "/knowledge",
  "/dashboards",
  "/onboarding",
];

// Next requires `config.matcher` to remain statically analyzable, while this
// runtime list decides whether an authenticated redirect applies. Keep the
// two positive lists aligned when a console route is added.

function isConsolePath(pathname: string): boolean {
  return CONSOLE_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/** Attach whatever cookies/headers the working response picked up (a rotated
 * session, GoTrue's no-cache headers) onto the response actually being
 * returned - a redirect built fresh with `NextResponse.redirect` starts with
 * none of that, and dropping a just-rotated refresh token here would defeat
 * rotation for exactly the request that triggered it. */
function carryOver(from: NextResponse, to: NextResponse): NextResponse {
  from.cookies.getAll().forEach((cookie) => to.cookies.set(cookie));
  from.headers.forEach((value, key) => to.headers.set(key, value));
  return to;
}

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const { supabaseUrl, supabaseAnonKey } = serverPublicConfig();
  // supabase-js derives the session's cookie name from the URL it is given -
  // `sb-${hostname-first-label}-auth-token` - and the browser always builds
  // its client from the PUBLIC url. A server-side fetch from inside the
  // frontend container can't reach `localhost` (SUPABASE_INTERNAL_URL below
  // points it at the auth-proxy service instead, mirroring API_INTERNAL_URL
  // in lib/tenant.ts) - fetching through a different host must not also
  // change which cookie this proxy reads and writes, so the name is pinned to
  // the public url regardless of which url actually answers the request.
  const cookieName = `sb-${new URL(supabaseUrl).hostname.split(".")[0]}-auth-token`;
  const fetchUrl = process.env.SUPABASE_INTERNAL_URL || supabaseUrl;

  let response = NextResponse.next({ request });

  const supabase = createServerClient(fetchUrl, supabaseAnonKey, {
    cookieOptions: { name: cookieName, ...authCookieOptions() },
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        // Written on the incoming request too, not just the response: a
        // Server Component rendered for THIS request reads cookies() off the
        // request, not off whatever this proxy returns.
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        Object.entries(headers ?? {}).forEach(([key, value]) => response.headers.set(key, value));
      },
    },
  });

  // Triggers the same refresh-before-render the official @supabase/ssr
  // middleware pattern calls for (its own README: "refreshes the session
  // before the page renders"). Falls back to a live GoTrue call under HS256
  // (local dev has no JWKS to check locally against); hosted Supabase's
  // ES256 tokens verify against the cached JWKS instead.
  const { data } = await supabase.auth.getClaims();
  const signedIn = Boolean(data?.claims);

  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/admin")) {
    // /admin/login handles its own redirect once signed in - it first checks
    // GET /api/platform/ping and only then leaves the form (admin/login/
    // page.tsx), because a signed-in tenant owner is not a platform admin.
    // Redirecting here on session alone, with no such check, would bounce
    // that owner into /admin, whose console layout immediately bounces them
    // back out - an infinite loop between the two guards. Every OTHER admin
    // page still needs a session before it loads at all.
    if (pathname !== "/admin/login" && !signedIn) {
      return carryOver(response, NextResponse.redirect(new URL("/admin/login", request.url)));
    }
    return response;
  }

  if (pathname === "/login") {
    if (signedIn) {
      return carryOver(response, NextResponse.redirect(new URL("/onboarding", request.url)));
    }
    return response;
  }

  if (isConsolePath(pathname) && !signedIn) {
    return carryOver(response, NextResponse.redirect(new URL("/login", request.url)));
  }

  return response;
}
