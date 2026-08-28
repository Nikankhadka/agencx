import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { authCookieOptions } from "./auth-cookie";
import { readPublicConfig } from "./public-config";

let client: SupabaseClient | null = null;

/**
 * Browser Supabase client (T-004; cookie-backed sessions since the auth
 * migration off self-minted tokens). Lazy singleton so importing this module
 * never throws at build time when env vars are absent (e.g. CI builds);
 * callers only pay the check when auth is actually used.
 *
 * `createBrowserClient` (not plain `createClient`) is what makes the session
 * live in a cookie (`sb-<host>-auth-token`) rather than localStorage - the
 * same cookie `src/proxy.ts` reads server-side, which is the whole point:
 * without it there is nothing for a server-rendered redirect to check.
 *
 * Config comes from the runtime values the root layout writes into the page,
 * not from build-time NEXT_PUBLIC_* inlining - see lib/public-config.ts.
 */
export function getSupabase(): SupabaseClient {
  if (client) return client;
  const { supabaseUrl, supabaseAnonKey } = readPublicConfig();
  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      "SUPABASE_URL and SUPABASE_ANON_KEY must be set on the server (see .env.example)"
    );
  }
  client = createBrowserClient(supabaseUrl, supabaseAnonKey, {
    cookieOptions: authCookieOptions(),
  });
  return client;
}
