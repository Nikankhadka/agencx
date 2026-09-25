/**
 * T-026: the header set. The CSP stays report-only until T-027, so the
 * enforcing header must not appear yet - a test that fails on the day someone
 * flips it without walking the pages first.
 */
import { describe, expect, it } from "vitest";

import { contentSecurityPolicy, securityHeaders } from "@/lib/security-headers";

const byKey = (dev: boolean) => Object.fromEntries(securityHeaders(dev).map((h) => [h.key, h.value]));

describe("securityHeaders", () => {
  it("sets the six static headers", () => {
    const h = byKey(false);
    expect(h["X-Content-Type-Options"]).toBe("nosniff");
    expect(h["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    expect(h["X-Frame-Options"]).toBe("SAMEORIGIN");
    expect(h["Permissions-Policy"]).toBe("camera=(), microphone=(), geolocation=(), payment=()");
    expect(h["Cross-Origin-Opener-Policy"]).toBe("same-origin");
    expect(h["Strict-Transport-Security"]).toBe("max-age=63072000; includeSubDomains");
  });

  it("never preloads HSTS", () => {
    expect(byKey(false)["Strict-Transport-Security"]).not.toMatch(/preload/i);
  });

  it("ships the CSP report-only, not enforced", () => {
    const h = byKey(false);
    expect(h["Content-Security-Policy-Report-Only"]).toBeTruthy();
    expect(h).not.toHaveProperty("Content-Security-Policy");
  });
});

describe("contentSecurityPolicy", () => {
  it("allows the storefront video embeds", () => {
    const csp = contentSecurityPolicy(false);
    expect(csp).toContain("frame-src https://www.youtube-nocookie.com https://player.vimeo.com");
  });

  it("forbids plugins, base rewrites and framing by other origins", () => {
    const csp = contentSecurityPolicy(false);
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("base-uri 'none'");
    expect(csp).toContain("frame-ancestors 'self'");
  });

  it("allows eval and local Supabase only in development", () => {
    const dev = contentSecurityPolicy(true);
    const prod = contentSecurityPolicy(false);
    expect(dev).toContain("'unsafe-eval'");
    expect(dev).toContain("http://localhost:54321");
    expect(prod).not.toContain("'unsafe-eval'");
    expect(prod).not.toContain("localhost");
  });
});
