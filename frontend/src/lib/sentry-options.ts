/**
 * Sentry init options shared by the server (`instrumentation.ts`) and the browser
 * (`instrumentation-client.ts`), so the privacy stance lives in exactly one place.
 *
 * Sentry v11 has no `sendDefaultPii`. Privacy is governed by `dataCollection`,
 * and its defaults are all ON (cookies, headers, request bodies, query strings,
 * user info, stack-frame variables). Left alone, an unhandled error while a
 * customer is on a storefront would ship their session cookie and whatever the
 * request carried. So everything is switched off explicitly; a new SDK default
 * cannot widen what leaves the process without this file changing.
 *
 * What is deliberately NOT here, and must never be added on the customer surface:
 * `replayIntegration()` / `replaysSessionSampleRate`. Replay would record a person
 * typing their name and phone number into the chat box.
 *
 * ponytail: no `withSentryConfig`, so no source-map upload and browser frames are
 * minified. That is the only setup that works in a container build with no build
 * args and no auth token. Upgrade path: a CI step running `sentry-cli sourcemaps
 * upload` against the `next build` output the frontend job already produces, with
 * `release` set to the commit SHA on both the upload and `Sentry.init`.
 */

const PRIVACY_OPTIONS = {
  // Tracing belongs to Langfuse on the backend; spans would only burn the error quota.
  tracesSampleRate: 0,
  dataCollection: {
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
  },
};

export interface SentryRuntimeOptions {
  environment?: string;
  release?: string;
}

/** The options to pass to `Sentry.init`, or `undefined` when no DSN is set (Sentry off). */
export function sentryInitOptions(dsn: string, runtime: SentryRuntimeOptions = {}) {
  if (!dsn) return undefined;
  return { ...PRIVACY_OPTIONS, dsn, ...runtime };
}
