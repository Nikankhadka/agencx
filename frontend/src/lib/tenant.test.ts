import { describe, expect, it, vi } from "vitest";

/**
 * RF-7 robustness: `resolveViewerSlug` is UX-only owner detection on the
 * customer surface, so ANY failure - a malformed public config, a bad URL, a
 * corrupt session cookie - must degrade to null (anonymous) rather than 500
 * the page. These cover the paths before the old try block: config and the
 * cookie-name URL derivation.
 */
const { serverPublicConfigMock } = vi.hoisted(() => ({
  serverPublicConfigMock: vi.fn(),
}));

vi.mock("./public-config", () => ({ serverPublicConfig: serverPublicConfigMock }));
vi.mock("next/headers", () => ({
  cookies: async () => ({ getAll: () => [] }),
  headers: async () => new Headers(),
}));

import { resolveViewerSlug } from "./tenant";

describe("resolveViewerSlug", () => {
  it("degrades to null when the public config cannot be read", async () => {
    serverPublicConfigMock.mockImplementation(() => {
      throw new Error("malformed env");
    });

    await expect(resolveViewerSlug()).resolves.toBeNull();
  });

  it("degrades to null on a malformed supabase URL", async () => {
    serverPublicConfigMock.mockReturnValue({
      supabaseUrl: "not a url",
      supabaseAnonKey: "anon",
      sentryDsn: "",
    });

    await expect(resolveViewerSlug()).resolves.toBeNull();
  });
});
