# B-4: production image for the Vercel `frontend` service (vercel.json). The dev
# container is Dockerfile.dev (toolchain only, deps in a named volume, source
# bind-mounted); this one is self-contained and is the artifact that ships.

FROM node:24.19.0-bookworm-slim AS deps

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

FROM node:24.19.0-bookworm-slim AS builder

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* are inlined into the client bundle at BUILD time, not read at
# runtime, so they have to be present here rather than set on the running
# container. Empty NEXT_PUBLIC_API_URL is the deployed default and is load
# bearing: the callers read `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`,
# and `??` only falls back on null/undefined, so "" survives and every call
# becomes a relative /api/... on the same origin the backend service serves.
ARG NEXT_PUBLIC_API_URL=""
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY

RUN npm run build

FROM node:24.19.0-bookworm-slim AS runtime

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0

RUN useradd --create-home --uid 1000 nextjs

# `standalone` traces the server and its deps; `public` and `.next/static` are
# deliberately not gathered by it (they are meant for a CDN) and must be copied
# in beside the server for it to serve them - see the Next `output` docs.
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nextjs /app/public ./public

USER nextjs

EXPOSE 3000

# PORT is left to the host, same contract as backend/Dockerfile: Vercel routes
# to 80 unless PORT is set in project settings, and server.js honours PORT and
# HOSTNAME directly.
CMD ["node", "server.js"]
