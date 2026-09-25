import * as Sentry from "@sentry/nextjs";

import { serverPublicConfig } from "@/lib/public-config";
import { sentryInitOptions } from "@/lib/sentry-options";

/**
 * Server-side error tracking (node and edge). Off unless `SENTRY_DSN` is set,
 * like Langfuse on the backend, so local dev and CI never send anything.
 * The privacy stance lives in `sentry-options.ts`.
 */
export function register() {
  const options = sentryInitOptions(serverPublicConfig().sentryDsn, {
    environment: process.env.ENVIRONMENT ?? process.env.NODE_ENV,
    release: process.env.VERCEL_GIT_COMMIT_SHA,
  });
  if (!options) return;
  // `dataCollection.stackFrameVariables` filters what is captured; this is the
  // switch that stops the capture in the first place. It defaults off, but is
  // explicit so a reviewer can see the stance.
  Sentry.init({ ...options, includeLocalVariables: false });
}

/**
 * Next 16's hook for server render and route-handler errors - the ones that
 * otherwise only trip an `error.tsx` boundary and leave nothing in a log anyone
 * reads. A no-op while Sentry is uninitialised.
 *
 * Next's `request.path` carries the query string (`/blog?name=foo`) and Sentry
 * copies it verbatim into the event's `nextjs` context, which `dataCollection.
 * urlQueryParams: false` does not reach. Strip it here so the stance holds.
 */
export const onRequestError: typeof Sentry.captureRequestError = (error, request, context) =>
  Sentry.captureRequestError(error, { ...request, path: request.path.split("?")[0] }, context);
