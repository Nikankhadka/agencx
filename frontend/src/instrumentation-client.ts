import * as Sentry from "@sentry/nextjs";

import { readPublicConfig } from "@/lib/public-config";
import { sentryInitOptions } from "@/lib/sentry-options";

// Browser-side error tracking. Off unless the server handed down a DSN through
// the public-config script. Runs on the customer storefront on purpose: a chat
// widget error is the one most needed and otherwise invisible. Never add Session
// Replay here - see sentry-options.ts.
const options = sentryInitOptions(readPublicConfig().sentryDsn, {
  environment: process.env.NODE_ENV,
});
if (options) Sentry.init(options);
