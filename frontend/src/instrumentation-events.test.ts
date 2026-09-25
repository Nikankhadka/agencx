/**
 * T-025: what actually leaves the process. The SDK is started with a transport
 * that keeps envelopes in memory, an error is reported through the same
 * `onRequestError` Next calls, and the captured event is searched for the
 * customer's data. Mirrors the backend's test_sentry.py.
 */
import * as Sentry from "@sentry/nextjs";
import { afterAll, describe, expect, it } from "vitest";

import { onRequestError } from "@/instrumentation";
import { sentryInitOptions } from "@/lib/sentry-options";

const DSN = "https://publickey@o0.ingest.example.invalid/1";
const COOKIE = "sb-access-token=cookie-secret-value";
const BEARER = "Bearer eyJ-super-secret-token";
const PHONE = "0400000000";

const request = {
  path: `/acme-dental?phone=${PHONE}`,
  method: "GET",
  headers: { cookie: COOKIE, authorization: BEARER, "user-agent": "vitest" },
};
const context = {
  routerKind: "App Router",
  routePath: "/[slug]",
  routeType: "render",
  renderSource: "react-server-components",
  revalidateReason: undefined,
  renderType: undefined,
} as const;

type CapturedEvent = Record<string, unknown>;
// The slice of Sentry's Envelope tuple this test reads: [headers, [[itemHeader, payload]]].
type Envelope = [unknown, [{ type: string }, unknown][]];

afterAll(() => Sentry.close());

describe("what actually leaves the process", () => {
  // Order matters: this one must run while Sentry is still uninitialised.
  it("reports nothing and does not throw while Sentry is off", () => {
    expect(Sentry.getClient()).toBeUndefined();
    expect(() => onRequestError(new Error("boom"), request, context)).not.toThrow();
  });

  it("reports a server render error without cookies, auth headers or the query string", async () => {
    const events: CapturedEvent[] = [];
    const transport = () => ({
      send: async (envelope: Envelope) => {
        for (const [header, payload] of envelope[1]) {
          if (header.type === "event") events.push(payload as CapturedEvent);
        }
        return {};
      },
      flush: async () => true,
    });
    Sentry.init({ ...sentryInitOptions(DSN)!, transport });

    onRequestError(new Error("storefront blew up"), request, context);
    await Sentry.flush(2000);

    const [event] = events;
    expect(event).toBeDefined();
    // Control against a vacuous pass: the event is real and carries its route.
    expect((event.exception as { values: { value: string }[] }).values[0].value).toBe(
      "storefront blew up",
    );
    expect(JSON.stringify(event.contexts)).toContain("/acme-dental");

    const blob = JSON.stringify(event);
    expect(blob).not.toContain("cookie-secret-value");
    expect(blob).not.toContain("eyJ-super-secret-token");
    expect(blob).not.toContain(PHONE);
  });
});
