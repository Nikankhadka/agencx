/**
 * Public browser config, delivered at runtime instead of baked at build time.
 *
 * `NEXT_PUBLIC_*` values are inlined into the client bundle when `next build`
 * runs, which means they have to exist during the image build. Vercel builds
 * container services with `buildah build` and passes no `--build-arg`, so the
 * Dockerfile's ARG/ENV pair resolved to empty strings and the browser shipped
 * with no Supabase config at all. Nothing failed loudly: `getSupabase()` is a
 * lazy singleton, so the build succeeded and the owner surface only broke when
 * a component first asked for the client.
 *
 * So the server hands these to the browser instead. The root layout reads them
 * from runtime env - where Vercel *does* inject project env vars - and writes
 * them into the document; `readPublicConfig` picks them up on the client. Both
 * values are public by definition (they ship in the page either way), so this
 * changes what reaches the browser not at all, only when.
 */

export const PUBLIC_CONFIG_GLOBAL = "__AGENCX_PUBLIC_CONFIG__";

export interface PublicConfig {
  supabaseUrl: string;
  supabaseAnonKey: string;
}

/**
 * Server-side: the config to hand the browser.
 *
 * Reads the unprefixed vars first (runtime, the deployed path) and falls back
 * to the `NEXT_PUBLIC_*` ones so a local `.env.local` keeps working untouched.
 */
export function serverPublicConfig(): PublicConfig {
  return {
    supabaseUrl: process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    supabaseAnonKey:
      process.env.SUPABASE_ANON_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
  };
}

/**
 * Client-side: the config the server wrote into the document, falling back to
 * build-time inlining so `next dev` and the test environment behave as before.
 */
export function readPublicConfig(): PublicConfig {
  const injected =
    typeof window !== "undefined"
      ? (window as unknown as Record<string, PublicConfig | undefined>)[PUBLIC_CONFIG_GLOBAL]
      : undefined;
  if (injected?.supabaseUrl && injected.supabaseAnonKey) return injected;
  return {
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
  };
}
