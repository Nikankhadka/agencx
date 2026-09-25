/**
 * T-026: response security headers, applied to every route by `next.config.ts`.
 * A module of its own so the values are unit-testable - the config file only
 * wires them in.
 *
 * The CSP ships report-only (T-026) so a missed origin shows up as a console
 * report instead of a broken page; T-027 renames the header to enforce it.
 */

/**
 * ponytail: `script-src` keeps 'unsafe-inline'. `app/layout.tsx` injects a
 * runtime-valued inline script (the public config), which no hash can cover,
 * and nonces would need `proxy.ts` on every route - it deliberately never runs
 * on the customer surface. Ceiling: this CSP stops injected third-party
 * sources and exfiltration destinations, not injected inline script. Upgrade
 * path: serve the public config from a route handler or a data attribute
 * instead of an inline script, then set `script-src 'self'` with no inline.
 */
export function contentSecurityPolicy(dev: boolean): string {
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    // React Refresh evals in `next dev`; production never needs it.
    "script-src": ["'self'", "'unsafe-inline'", ...(dev ? ["'unsafe-eval'"] : [])],
    "style-src": ["'self'", "'unsafe-inline'"],
    // Tenant media is served from Cloudinary; the cover comes through the API.
    "img-src": ["'self'", "data:", "blob:", "https://res.cloudinary.com"],
    "media-src": ["'self'", "https://res.cloudinary.com"],
    // Storefront video embeds (Storefront.tsx videoEmbedUrl).
    "frame-src": ["https://www.youtube-nocookie.com", "https://player.vimeo.com"],
    "font-src": ["'self'", "data:"],
    // The browser reaches the backend through the same-origin /api rewrite,
    // Supabase auth directly, and Sentry for error reports. Local Supabase
    // sits behind the auth-proxy on :54321.
    "connect-src": [
      "'self'",
      "https://*.supabase.co",
      "https://*.sentry.io",
      ...(dev ? ["http://localhost:54321"] : []),
    ],
    "worker-src": ["'self'", "blob:"],
    "frame-ancestors": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'none'"],
    "form-action": ["'self'"],
  };
  return Object.entries(directives)
    .map(([name, sources]) => `${name} ${sources.join(" ")}`)
    .join("; ");
}

export function securityHeaders(dev: boolean): { key: string; value: string }[] {
  return [
    // The app proxies user-supplied bytes (cover route, uploads).
    { key: "X-Content-Type-Options", value: "nosniff" },
    // A storefront URL carries the tenant slug.
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    // SAMEORIGIN everywhere, storefront included: embedding a storefront is a
    // per-tenant decision a static config cannot express.
    { key: "X-Frame-Options", value: "SAMEORIGIN" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
    // No window.open or OAuth popup anywhere; auth is an emailed code.
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    // No `preload`: it is a one-way door for every subdomain.
    { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
    { key: "Content-Security-Policy-Report-Only", value: contentSecurityPolicy(dev) },
  ];
}
