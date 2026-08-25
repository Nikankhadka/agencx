# Deploying Agencx

The one page for shipping Agencx to the internet on free infrastructure, with
push-to-deploy CI/CD. B-4 is the ticket that delivers it.

This supersedes two earlier plans: the AWS ECS/Terraform stack (`infra/*.tf`,
kept and dormant - still validated by CI so it cannot rot, deployed by nothing)
and the Google Cloud Run backend this page described before B-4. Both are
replaced by a single Vercel project running two container services.

## The stack

| Concern | Where | Cost |
|---|---|---|
| Frontend (Next.js 16, three surfaces) | Vercel, `frontend` container service | $0 |
| Backend (FastAPI) | Vercel, `backend` container service | $0 |
| DB + Auth (Postgres + pgvector + GoTrue + RLS) | hosted Supabase | $0 (7-day idle pause) |
| Chat LLM | Google AI Studio + Groq + OpenRouter | $0 |
| Embeddings | Google `text-embedding-004` | $0 / credits |
| Reranker | Cohere | $0 free tier |
| Login-in-chat email | SMTP relay (Resend/Brevo) or `console` | $0 |
| CI/CD | GitHub Actions (gate) + Vercel Git integration (deploy) | $0 |

Three decisions shape the rest:

1. **One project, two services, one origin.** `vercel.json` declares a
   `frontend` and a `backend` service, each built from its own Dockerfile, and
   rewrites `/api/*` and `/health` to the backend and everything else to the
   frontend. The browser therefore never makes a cross-origin request in
   production: no preflight, no CORS allowlist to maintain, and one hostname to
   point a domain at later (B-2).
2. The production image stays **lean** (no `sentence-transformers`/`torch`), so
   embeddings and reranking are hosted, not local. Embeddings use Google
   `text-embedding-004` truncated to 384 dims (matches the schema, no
   re-ingest); reranking uses Cohere.
3. The product ships on the **auto URL** first (`<project>.vercel.app`).
   Buying `agencx.app` and pointing it at the project is ticket B-2, deferred -
   nothing waits on it.

## Branches

| Branch | What it is | What Vercel does |
|---|---|---|
| `development` | integration; feature branches PR into it | preview deployment |
| `staging` | production | production deployment |

There is no `main`. `ci.yml` gates pushes to both branches and every PR;
`deploy.yml` fires after CI goes green on `staging` and smoke-tests the live
origin.

## What you can see with the auto URL

**All three surfaces, on the one URL.** Since D22 the surfaces are paths, not
hosts, so a single `<project>.vercel.app` serves the whole product:

- **tenant-admin** at `<project>.vercel.app` (`/login`, `/home`, ...)
- **customer** at `<project>.vercel.app/{slug}` - the real product link
- **platform** at `<project>.vercel.app/admin`

This is what D22 bought: the customer page used to be unreachable on this deploy
because Vercel's free tier has no wildcard subdomains, and it sat behind a
wildcard certificate nobody had purchased. There is no DNS step left in the way.

## Prerequisites

- A Supabase account.
- A Vercel account.
- Free API keys: Google AI Studio, Cohere, optionally Groq + OpenRouter.
- Push access to the GitHub repo.

## Step 1 - Supabase

1. Create a new hosted project. Note these values:
   - `SUPABASE_URL` and `SUPABASE_ANON_KEY` (Project Settings > API).
   - `SUPABASE_JWT_SECRET` (the JWT secret under Project Settings > API).
   - The database connection string. Use the pooler host, but the
     **session** port (`5432`), not the transaction port (`6543`). Supavisor's
     transaction mode does not support prepared statements and asyncpg uses
     them everywhere; on `6543` both the migration runner and the app pool die
     with a "cannot insert multiple commands into a prepared statement" style
     error. The pooler is still the right target - the direct host
     (`db.<ref>.supabase.co`) is IPv6-only and does not resolve from Vercel.
2. Apply migrations once, from a machine with this repo checked out:

   ```bash
   docker compose run --rm \
     -e DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres' \
     backend python -m app.shared.migrate
   ```

   This creates the schema, the `wren_app` role, and the pgvector indexes.
   pgvector is preinstalled on Supabase.
3. Seed the demo tenant, same shell (the deploy smoke test looks for it):

   ```bash
   docker compose run --rm \
     -e DATABASE_URL='<pooler url>' \
     backend python -m seeds.seed_tenant1_phoneshop
   ```

## Step 2 - Vercel

1. Import the GitHub repo. **Leave the root directory at the repo root** - not
   `frontend/`. `vercel.json` at the root is what declares the two services;
   pointing the project at `frontend/` hides it and you get a frontend-only
   deploy that 404s every `/api` call.
2. Set the **production branch to `staging`** (Settings > Git). `development`
   then produces preview deployments.
3. Do **not** set `PORT`. Vercel injects it per service (the frontend was
   observed listening on 80) and both images honour it. A project-level `PORT`
   would apply to both services and send one of them to the wrong socket.

## Step 3 - API keys (all free)

- Google AI Studio key -> `LLM_API_KEY` (also reused for embeddings).
- Cohere key -> `COHERE_API_KEY` (rerank).
- Optional: Groq key (`LLM_FALLBACK_API_KEY`) and OpenRouter key
  (`LLM_FAILOVER_API_KEY`) for the two failover legs.
- Email: create a Resend or Brevo free account and capture the SMTP
  host/port/user/pass, or leave `EMAIL_PROVIDER=console` to log codes instead of
  sending (demo-only).

## Step 4 - Environment variables

All of these are Vercel project environment variables. Set them for both
Production and Preview, or the preview deploys will boot against nothing.

Backend service:

```
DATABASE_URL=<Supabase session pooler string, port 5432>
WREN_APP_DB_PASSWORD=<8+ chars, no quotes/backslash/$>
SUPABASE_URL=<...>
SUPABASE_ANON_KEY=<...>
SUPABASE_JWT_SECRET=<...>
LLM_PROVIDER=openai_compat
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=<Google AI Studio key>
LLM_MODEL=gemini-3.5-flash-lite
LLM_FALLBACK_PROVIDER=openai_compat
LLM_FALLBACK_BASE_URL=https://api.groq.com/openai/v1
LLM_FALLBACK_API_KEY=<Groq key, optional>
LLM_FALLBACK_MODEL=openai/gpt-oss-120b
LLM_FAILOVER_PROVIDER=openai_compat
LLM_FAILOVER_BASE_URL=https://openrouter.ai/api/v1
LLM_FAILOVER_API_KEY=<OpenRouter key, optional>
LLM_FAILOVER_MODEL=google/gemma-4-26b-a4b-it:free
EMBEDDER=google
GOOGLE_EMBED_MODEL=text-embedding-004
EMBEDDING_DIM=384
RERANKER=cohere
COHERE_API_KEY=<Cohere key>
EMAIL_PROVIDER=smtp            # or console
EMAIL_SMTP_HOST=<...>          # when smtp
EMAIL_SMTP_PORT=587
EMAIL_SMTP_FROM=<...>
ENVIRONMENT=production
```

`EMBEDDER=local` and `RERANKER=local` are not available in production: the image
ships without those packages on purpose, and either value fails at first use
with `ModuleNotFoundError`, by design.

Frontend service - nothing extra. The browser gets its Supabase config from
`SUPABASE_URL` and `SUPABASE_ANON_KEY` above, read at request time by the root
layout and written into the page (`frontend/src/lib/public-config.ts`).

`NEXT_PUBLIC_*` is **not** usable here: those are inlined when `next build`
runs, which happens inside the image build, and Vercel builds container
services with `buildah build` passing no `--build-arg`. They would resolve to
empty strings. This is also why the root layout is `force-dynamic` - statically
prerendering it would freeze the build-time (empty) config into the HTML.

`NEXT_PUBLIC_API_URL` is deliberately **not set**. The callers read
`process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`, and the frontend
image defaults it to an empty string, which `??` preserves - so every API call
becomes a relative `/api/...` on the same origin the backend service serves.
Setting it to an absolute URL would reintroduce the cross-origin request the
whole topology exists to avoid.

## Step 5 - GitHub Actions secret

For `deploy.yml`'s smoke test:

```
SMOKE_TEST_BASE_URL=https://<project>.vercel.app
```

Until it is set the workflow no-ops with a notice rather than failing.

## What the repo changes deliver

The founder steps above are external. The code that makes them work is B-4
(`docs/agencx/spec/10-deploy.md`, branch `feat/deploy-containers-cicd`):

1. `vercel.json` - the two services and the rewrites that route them.
2. `frontend/Dockerfile` + `output: "standalone"` in `next.config.ts` - the
   frontend as a self-contained container.
3. `backend/Dockerfile` - retargeted off ECS, `PORT`-driven, plus a `test` stage
   CI runs the suite in.
4. `backend/app/llm/embedder.py` - a `GoogleEmbedder` (native `embedContent`,
   `outputDimensionality=384`) and a `'google'` branch in `get_embedder`;
   `backend/app/shared/config.py` accepts `'google'` and adds
   `google_embed_model`.
5. `backend/app/main.py` - `_ALLOWED_ORIGIN_REGEX` narrowed to `localhost`,
   because production is same-origin and has no preflight to allow.
6. `backend/app/features/knowledge/api.py` - the upload cap lowered to 4MB, so
   an oversized file gets the backend's own 422 rather than the platform's
   opaque 413.
7. `.github/workflows/` - `ci.yml` gates `staging`/`development` and runs the
   backend suite in the image's `test` stage; `deploy.yml` drops the AWS build
   and push entirely and smoke-tests the live origin instead.
8. `.env.example` - documents `EMBEDDER=google`, `RERANKER=cohere` and the
   pooler `DATABASE_URL`.

`ci.yml` remains the gate on every push and PR. `deploy.yml` fires via
`workflow_run` only after CI is green on `staging`.

## Verifying

1. Locally: `make check` and `make ci` stay green.
2. Locally, the two images that actually ship:

   ```bash
   docker build --target test -t wren-backend-test backend/   # what CI runs
   docker build -t wren-frontend frontend/
   ```

3. Push a branch -> PR into `development`: `ci.yml` passes.
4. Merge to `staging`: Vercel builds and deploys both services, then
   `deploy.yml` smoke-tests `/health`, `/api/public/tenant/bytefix` and
   `/bytefix` on the live origin.
5. Open `<project>.vercel.app` -> owner login -> onboarding -> go-live lands on
   Home. The seeded tenant's page renders at `<project>.vercel.app/bytefix`.

## Caveats to keep in mind

- **Settled on 2026-08-25, first real deploy.** Container services work on the
  hobby plan; the bare `root`/`entrypoint` pair is accepted and no
  `"runtime": "container"` key is needed. The `NEXT_PUBLIC_*` question resolved
  the other way from the guess above - Vercel passes no build args at all, so
  those values moved to runtime.
- **Supabase's `postgres` is not a superuser.** Migrations that rely on
  superuser waivers pass locally and fail there. Two showed up in 0003:
  `alter function ... owner to` needs membership in the receiving role, and
  needs that role to hold CREATE on the schema. Both grants now live in
  `0002_roles.sql`.
- **Supabase free tier pauses after 7 days idle** (architecture section 13).
  Fine for a portfolio; keep it warm or move to Pro ($25/month) if it bites.
- **Free-tier LLM and embedding models train on your inputs** (section 13). No
  real customer data through the free tiers; swap provider before a real cohort.
- **Google's `thought_signature` 400** (known gap in `progress.md`) can reject
  multi-tool turns on the primary tier; it is a separate ticket, not a deploy
  concern, but may surface live.
- **B-2** (buy `agencx.app`, point it here) is the real domain launch; the
  `vercel.app` origin here is its stand-in. It is a single DNS record now - D22
  removed the wildcard, and the same-origin topology removed the CORS half of
  the ticket.
