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
   - The database connection string. Use the **transaction pooler** string
     (port `6543`) - the serverless container gets a fresh IP per instance and
     Supavisor is what makes that survivable.
2. Apply migrations once, from a machine with this repo checked out:

   ```bash
   docker compose run --rm \
     -e DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres' \
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
3. Set the `backend` service's port to **8000** if the project offers a port
   setting; otherwise set `PORT` as a backend env var in Step 4. Neither image
   bakes a port - the host decides, and the container listens wherever `PORT`
   says.

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
PORT=8000
DATABASE_URL=<Supabase transaction pooler string, port 6543>
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

Frontend service - two values, both `NEXT_PUBLIC_`, inlined into the browser
bundle at **build** time, so they must exist before the first deploy:

```
NEXT_PUBLIC_SUPABASE_URL=<...>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<...>
```

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

- **Vercel container services are a young feature.** If the first build ignores
  the Dockerfiles, add `"runtime": "container"` to each service in
  `vercel.json` - the docs show both that form and the bare
  `root`/`entrypoint` pair this repo uses.
- **Check the built bundle for the Supabase URL after the first deploy.**
  `frontend/Dockerfile` declares `NEXT_PUBLIC_*` as build args and re-exports
  them as `ENV`. If Vercel supplies project env vars to the build as
  environment rather than as build args, that `ENV` line overwrites them with
  empty strings and the browser bundle ships with no Supabase URL. The fix is
  to drop the forced `ENV` for those two and let the build environment provide
  them.
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
