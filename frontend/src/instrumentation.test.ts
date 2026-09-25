/**
 * T-025: frontend error tracking, init contract - off without a DSN, the
 * restrictive options, the DSN delivery seam. What actually leaves the process
 * is checked in instrumentation-events.test.ts (one SDK init per file: the
 * Node SDK keeps global state that a second init in the same process does not
 * cleanly replace).
 */
import * as Sentry from "@sentry/nextjs";
import { afterEach, describe, expect, it, vi } from "vitest";

import { register } from "@/instrumentation";
import { readPublicConfig, serverPublicConfig } from "@/lib/public-config";
import { sentryInitOptions } from "@/lib/sentry-options";

const DSN = "https://publickey@o0.ingest.example.invalid/1";

afterEach(async () => {
  await Sentry.close();
  vi.unstubAllEnvs();
});

describe("init contract", () => {
  it("creates no options, so no client, without a DSN", () => {
    expect(sentryInitOptions("")).toBeUndefined();
  });

  it("register() leaves Sentry uninitialised when SENTRY_DSN is unset", () => {
    vi.stubEnv("SENTRY_DSN", undefined);
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", undefined);
    register();
    expect(Sentry.getClient()).toBeUndefined();
  });

  it("register() starts a client that collects nothing extra when a DSN is set", () => {
    vi.stubEnv("SENTRY_DSN", DSN);
    register();
    // includeLocalVariables is a node-only option, absent from the shared client type.
    const options = Sentry.getClient()?.getOptions() as Record<string, unknown> | undefined;
    expect(options?.dsn).toBe(DSN);
    expect(options?.tracesSampleRate).toBe(0);
    expect(options?.includeLocalVariables).toBe(false);
    expect(options?.dataCollection).toEqual({
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
      graphQL: { document: false, variables: false },
      genAI: { inputs: false, outputs: false },
      databaseQueryData: false,
      queues: false,
      stackFrameVariables: false,
      frameContextLines: 0,
    });
  });

  it("never enables Session Replay", () => {
    const options = sentryInitOptions(DSN) as Record<string, unknown>;
    expect(options).not.toHaveProperty("replaysSessionSampleRate");
    expect(options).not.toHaveProperty("replaysOnErrorSampleRate");
    expect(options).not.toHaveProperty("integrations");
  });
});

describe("DSN delivery to the browser", () => {
  it("prefers the runtime var and falls back to NEXT_PUBLIC_", () => {
    vi.stubEnv("SENTRY_DSN", undefined);
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", undefined);
    expect(serverPublicConfig().sentryDsn).toBe("");

    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "https://public@example.invalid/2");
    expect(serverPublicConfig().sentryDsn).toBe("https://public@example.invalid/2");
    expect(readPublicConfig().sentryDsn).toBe("https://public@example.invalid/2");

    vi.stubEnv("SENTRY_DSN", DSN);
    expect(serverPublicConfig().sentryDsn).toBe(DSN);
  });
});
