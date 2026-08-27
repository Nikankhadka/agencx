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
| Login-in-chat email | SMTP relay (Brevo) or `console` | $0 |
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

**One branch deploys. Nothing else does.**

| Branch | What it is | What Vercel does | URL |
|---|---|---|---|
| `staging` | production - always live | production deployment | `<project>.vercel.app`, later `agencx.app` (B-2) |
| `development` | integration; work happens here and locally | **nothing** | - |
| `feat/*` | in-flight work | **nothing** | - |

There is no `main`. `ci.yml` gates pushes to `staging` and `development` and
every PR; `deploy.yml` fires after CI goes green on `staging` and smoke-tests
the live origin.

Two settings produce that table, and both are needed. **Both are project
settings in the dashboard. Neither belongs in `vercel.json` - see the warning
below.**

1. Settings > Git > **Production Branch = `staging`**. This is what makes a push
   to `staging` a *production* deployment rather than a preview. It is the one
   setting here with no API at all: `PATCH /v9/projects/{id}` rejects
   `productionBranch` as an unknown property on every API version, and
   `POST /v9/projects/{id}/link` accepts the field and ignores it, re-deriving
   the branch from the repo's GitHub default. Set it in the dashboard. It *can*
   be read back, as `link.productionBranch` on the project object.
2. Settings > Git > **Ignored Build Step** = Custom, with
   `[ "$VERCEL_GIT_COMMIT_REF" != "staging" ]`. Vercel reads exit 0 as "ignore
   this build" and exit 1 as "build it", so `staging` builds and every other
   branch is skipped before a build starts. Without this, Production Branch
   alone still burns a preview build on every `development` and `feat/*` push
   and publishes a preview URL for it. Readable and writable over the API as
   `commandForIgnoringBuildStep`.

   One consequence worth knowing: a deploy started from the CLI has no git ref,
   so `VERCEL_GIT_COMMIT_REF` is empty and the build is skipped like any other
   non-`staging` branch. This project deploys through the Git integration only,
   so that is the correct behaviour rather than a limitation - but it will look
   like a hang if you ever reach for `vercel --prod`.

> **Do not put `ignoreCommand` in `vercel.json`.** It is a documented key, but a
> `vercel.json` that also declares `services` (this one does - the two container
> services) is rejected wholesale when it is present. The failure gives you
> nothing to debug: the GitHub commit status goes to `Vercel - Deployment
> failed.` within seconds of the push, `target_url` is `null`, and **no
> deployment record is created at all**, so the dashboard and
> `GET /v6/deployments` both look as though the push never happened. It cost
> three branches - `8c0edf5` (feat), `a869169` (development) and `5b68822`
> (staging) each failed that way on 2026-08-26, while `558898b`, the last commit
> before the key was added, deployed fine twice. `git.deploymentEnabled` was
> considered as the replacement and rejected: it takes an explicit branch map
> and would need a new entry for every future branch, where the Ignored Build
> Step is one condition that needs no maintenance.

Note that Vercel marks the **first** deployment of a freshly imported project as
production regardless of which branch it came from. If the dashboard shows one
old production deployment from an unrelated branch, that is what it is.

There is deliberately **one Supabase project** behind this, shared by nothing
else because nothing else deploys. The tradeoff is real and accepted while the
audience is the founder: a bad migration reaches live data immediately, with no
second environment to catch it in first. Revisit before onboarding a real tenant.

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

Create one hosted project. It backs the deployed stack; local dev keeps using
`docker compose up -d db` and never touches it.

1. Note these values:
   - `SUPABASE_URL` and `SUPABASE_ANON_KEY` (Project Settings > API).
   - `SUPABASE_SERVICE_ROLE_KEY` (same page). The backend presents it to GoTrue's
     Admin API and to Storage. A project created since Supabase moved to ES256
     session signing has no symmetric secret to mint a service token from, so the
     real key is the only way in. Server-side only - it never reaches the browser.
   - `SUPABASE_JWT_SECRET` (the JWT secret under Project Settings > API).
   - The database connection string. Use the pooler host, but the
     **session** port (`5432`), not the transaction port (`6543`). Supavisor's
     transaction mode does not support prepared statements and asyncpg uses
     them everywhere; on `6543` both the migration runner and the app pool die
     with a "cannot insert multiple commands into a prepared statement" style
     error. The pooler is still the right target - the direct host
     (`db.<ref>.supabase.co`) is IPv6-only and does not resolve from Vercel.
2. Create a private Storage bucket for uploads (Storage > New bucket). Its name
   becomes `UPLOADS_BUCKET`. Without it the backend falls back to local disk, and
   a document attached during onboarding is gone by the time the owner saves:
   the upload and the chunk-and-embed pass are two different requests, and a
   container host does not promise they land on the same instance. The failure is
   silent - the document is just marked failed.
3. Apply migrations once, from a machine with this repo checked out:

   ```bash
   docker compose run --rm \
     -e DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres' \
     backend python -m app.shared.migrate
   ```

   This creates the schema, the `wren_app` role, and the pgvector indexes.
   pgvector is preinstalled on Supabase.
4. Seed the demo tenant, same shell (the deploy smoke test looks for it):

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
2. Set the **production branch to `staging`** (Settings > Git). Together with
   the **Ignored Build Step** (Settings > Git, see Branches above), that makes
   `staging` the only branch that deploys at all.
3. Do **not** set `PORT`. Vercel injects it per service (the frontend was
   observed listening on 80) and both images honour it. A project-level `PORT`
   would apply to both services and send one of them to the wrong socket.
4. Settings > Functions > **Region = the same region as the Supabase project**
   (`syd1` for `ap-southeast-2`). This one is easy to skip and expensive to
   leave wrong. A new project defaults to `iad1` (Washington DC); with the
   database in Sydney, every query crossed the Pacific and came back, and the
   backend makes several per request - a first login alone does six (count,
   insert, fetchrow, update, the GoTrue admin call, tenant resolve, tenant
   create). Measured on 2026-08-26 with the split in place: `/health`, which
   runs one `select 1`, took ~700ms warm. `x-vercel-id` on any response names
   the regions it travelled through, so `syd1::iad1::` is the symptom and
   `syd1::syd1::` is the fix. Writable over the API as
   `serverlessFunctionRegion`, and it applies from the next build. A non-default
   region is allowed on the hobby plan.

## Step 3 - API keys (all free)

- Google AI Studio key -> `LLM_API_KEY` (also reused for embeddings).
- Cohere key -> `COHERE_API_KEY` (rerank).
- Optional: Groq key (`LLM_FALLBACK_API_KEY`) and OpenRouter key
  (`LLM_FAILOVER_API_KEY`) for the two failover legs.
- Email: **use Brevo**, not Resend, until B-2 buys `agencx.app`. Resend delivers
  only to your own account email until you verify a domain you own, which makes
  it useless for showing anyone else. Brevo allows a verified *single sender*
  with no domain at all: 300/day free, host `smtp-relay.brevo.com`, port 587,
  username your Brevo login, password a generated SMTP key (not your account
  password). Capture host/port/user/pass for step 4.

  Port 465 (implicit TLS) is not supported: `SmtpEmailProvider` uses
  `smtplib.SMTP` plus `starttls()`, which is the 587 shape. Every relay in play
  offers 587, so this is a documented limit rather than a gap worth code.

  Leaving `EMAIL_PROVIDER=console` is demo-only and has a sharp edge - see the
  warning under step 4.

## Step 4 - Environment variables

All of these are Vercel project environment variables. With one database and one
deployed branch they hold a single value each - but tick **both Production and
Preview** anyway. It costs nothing, and it means a preview that ever does run
(after the Ignored Build Step setting changes, or a manual deploy) is not
   broken by omission.

Backend service:

```
DATABASE_URL=<Supabase session pooler string, port 5432>
WREN_APP_DB_PASSWORD=<8+ chars, no quotes/backslash/$>
SUPABASE_URL=<...>
SUPABASE_ANON_KEY=<...>
SUPABASE_JWT_SECRET=<...>
SUPABASE_SERVICE_ROLE_KEY=<...>
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
UPLOADS_BUCKET=<Storage bucket name from step 1>
EMAIL_PROVIDER=smtp            # console logs the code instead of sending it
EMAIL_SMTP_HOST=smtp-relay.brevo.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_FROM=<your verified Brevo single sender>
EMAIL_SMTP_USER=<...>          # required by every hosted relay
EMAIL_SMTP_PASSWORD=<...>      # the generated SMTP key, not the account password
ENVIRONMENT=production
```

`GOOGLE_EMBED_MODEL` is not in the list because `config.py` already defaults it
to `text-embedding-004`; set it only to move off that model.

Every one of these is load-bearing, but four of them fail in ways that do not
look like a missing variable, so check them by name after any project rebuild:
`COHERE_API_KEY` (a 401 from the reranker on every grounded answer, while
`RERANKER=cohere` is set and looks fine), `SUPABASE_SERVICE_ROLE_KEY`, and the
`EMAIL_SMTP_*`/`EMAIL_PROVIDER` pair - see the two warnings below.

`EMBEDDER=local` and `RERANKER=local` are not available in production: the image
ships without those packages on purpose, and either value fails at first use
with `ModuleNotFoundError`, by design.

`EMAIL_PROVIDER` deserves the same warning, and it is the default that bites:
unset, it is `console`, which **logs the login code to the platform's log stream
instead of sending it**. The request still answers `202`, because the endpoint
did accept it - so login looks like it works and no code ever arrives. The
captured-code escape hatch (`/api/auth/dev-login-code`) is gated to
`ENVIRONMENT=local` on purpose, so on a deploy there is no other way to obtain a
code: `console` means nobody can log in at all.

`UPLOADS_BUCKET` is not optional here either, and unlike those two it fails
quietly. Left empty, `app/shared/storage.py` selects `LocalStorage` and the
container writes uploads to a disk the next request may not see - so onboarding's
"attach a document" step appears to work and the document is marked failed later.
Empty is correct only where the filesystem persists, which is local dev and the
test suite.

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

```
SMOKE_TEST_BASE_URL=https://<project>.vercel.app
```

**Set it.** Two workflows read this one secret and both are written to no-op
with a notice rather than fail while it is unset, which makes "not set" look
exactly like "passing": `deploy.yml` never verifies the origin, and
`keep-warm.yml` runs its cron every 10 minutes and pings nothing, so the cold
start it exists to hide is never actually hidden. It went unset from B-4 until
2026-08-26 and neither workflow ever went red.

## What the repo changes deliver

The founder steps above are external. The code that makes them work is B-4
(`docs/agencx/spec/10-deploy.md`, branch `feat/deploy-containers-cicd`):

1. `vercel.json` - the two services and the rewrites that route them. The
   branch filter lives in the dashboard as the Ignored Build Step, not here -
   see the warning under Branches.
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

3. Push a branch -> PR into `development`: `ci.yml` passes, and Vercel builds
   **nothing**. A deployment appearing here means the Ignored Build Step is not
   taking effect.
4. Merge to `staging`: Vercel builds and deploys both services with
   `target: "production"`, then `deploy.yml` smoke-tests `/health`,
   `/api/public/tenant/bytefix` and `/bytefix` on the live origin.
5. Open `<project>.vercel.app` -> owner login, with the code arriving in a real
   inbox -> onboarding, attaching a document -> go-live lands on Home. The seeded
   tenant's page renders at `<project>.vercel.app/bytefix`.
6. Ask for a sixth login code for one address inside an hour: it answers 429,
   not a sixth email.

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
- **Container services scale to zero.** The first request after an idle gap pays
  the container boot - ~11s measured on 2026-08-26, against ~1.2s warm. That is
  inherent to the plan, not a fault: `.github/workflows/keep-warm.yml` pings
  `/health` every 10 minutes so a visitor is unlikely to be the one who wakes it,
  which hides the symptom rather than removing it. Delete that workflow if the
  project ever moves to a plan that keeps an instance up.
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
