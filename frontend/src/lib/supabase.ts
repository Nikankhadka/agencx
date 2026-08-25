import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { readPublicConfig } from "./public-config";

let client: SupabaseClient | null = null;

/**
 * Browser Supabase client (T-004). Lazy singleton so importing this module
 * never throws at build time when env vars are absent (e.g. CI builds);
 * callers only pay the check when auth is actually used.
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
  client = createClient(supabaseUrl, supabaseAnonKey);
  return client;
}
