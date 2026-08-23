# Deploying Agencx

The one page for shipping Agencx to the internet on free infrastructure, with
push-to-deploy CI/CD. This supersedes the dormant AWS ECS/Terraform path
(`infra/*.tf`, and the AWS half of `.github/workflows/deploy.yml`, which
currently no-op) with a stack that is actually free to run.

## The stack

| Concern | Where | Cost |
|---|---|---|
| Frontend (Next.js 16, three surfaces) | Vercel Hobby | $0 |
| Backend (FastAPI) | Google Cloud Run (project `agencx`) | free tier + credits |
| DB + Auth (Postgres + pgvector + GoTrue + RLS) | hosted Supabase | $0 (7-day idle pause) |
| Chat LLM | Google AI Studio + Groq + OpenRouter | $0 |
| Embeddings | Google `text-embedding-004` | $0 / credits |
| Reranker | Cohere | $0 free tier |
| Login-in-chat email | SMTP relay (Resend/Brevo) or `console` | $0 |
| CI/CD | GitHub Actions + Vercel Git integration | $0 |

Two decisions shape the rest:

1. The production image stays **lean** (no `sentence-transformers`/`torch`), so
   embeddings and reranking are hosted, not local. Embeddings use Google
   `text-embedding-004` truncated to 384 dims (matches the schema, no
   re-ingest); reranking uses Cohere.
2. We ship on **auto URLs first** (`<project>.vercel.app` and
   `<service>.run.app`). The wildcard `{slug}.agencx.app` domain move is ticket
   B-2, deferred.

## What you can see with auto URLs

Surface routing is host-based (`frontend/src/lib/tenant.ts` +
`frontend/src/proxy.ts`): `admin.*` -> platform, `app.*` -> tenant-admin,
`{slug}.*` -> customer, bare base -> tenant-admin. Vercel's free tier gives a
single `<project>.vercel.app` with no wildcard subdomains, so:

- **tenant-admin** (owner login/onboarding) works at the bare Vercel URL.
- **customer** (`{slug}`) and **platform** (`admin.*`) need a wildcard custom
  domain - that is B-2, which this deploy does not do.

This deploy proves the pipeline and the owner surface live; the customer-facing
`{slug}` link goes live when B-2 wires `*.agencx.app`.

## Prerequisites

- A Google Cloud project named `agencx` with billing (credits fine).
- A Supabase account.
- A Vercel account.
- Free API keys: Google AI Studio, Cohere, optionally Groq + OpenRouter.
- Push access to the GitHub repo.

## Step 1 - Supabase

1. Create a new hosted project. Note these values:
   - `SUPABASE_URL` and `SUPABASE_ANON_KEY` (Project Settings > API).
   - `SUPABASE_JWT_SECRET` (the JWT secret under Project Settings > API).
   - The database connection string. Use the **transaction pooler** string
     (port `6543`) - Cloud Run needs IPv4, and Supavisor provides it.
2. Apply migrations once, from a machine with this repo checked out:

   ```bash
   cd backend
   DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres' \
     uv run python -m app.shared.migrate
   ```

   This creates the schema, the `wren_app` role, and the pgvector indexes.
   pgvector is preinstalled on Supabase.
3. Optional demo tenant, same shell:

   ```bash
   DATABASE_URL='<pooler url>' uv run python -m seeds.seed_tenant1_phoneshop
   ```

## Step 2 - Google Cloud Run (project `agencx`)

1. Enable the APIs: Cloud Run, Artifact Registry, IAM Credentials.
2. Create an Artifact Registry repository for the backend image, e.g.
   `backend` in region `us-central1`:

   ```bash
   gcloud artifacts repositories create backend \
     --repository-format=docker --location=us-central1 --project=agencx
   ```

3. Create a service account for the deploy pipeline:

   ```bash
   gcloud iam service-accounts create github-deploy --project=agencx
   gcloud projects add-iam-policy-binding agencx \
     --member="serviceAccount:github-deploy@agencx.iam.gserviceaccount.com" \
     --role=roles/run.admin
   gcloud projects add-iam-policy-binding agencx \
     --member="serviceAccount:github-deploy@agencx.iam.gserviceaccount.com" \
     --role=roles/iam.serviceAccountUser
   gcloud projects add-iam-policy-binding agencx \
     --member="serviceAccount:github-deploy@agencx.iam.gserviceaccount.com" \
     --role=roles/artifactregistry.writer
   ```

4. Wire GitHub to that service account with Workload Identity Federation (OIDC)
   so the workflow uses no long-lived key:

   ```bash
   gcloud iam workload-identity-pools create github-pool \
     --location=global --project=agencx
   gcloud iam workload-identity-pools providers create-oidc github-provider \
     --location=global --project=agencx \
     --workload-identity-pool=github-pool \
     --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
     --issuer-uri="https://token.actions.githubusercontent.com" \
     --allowed-audiences="https://github.com/Nikankhadka"
   gcloud iam service-accounts add-iam-policy-binding \
     github-deploy@agencx.iam.gserviceaccount.com --project=agencx \
     --role=roles/iam.workloadIdentityUser \
     --member="principalSet://iam.googleapis.com/projects/$(gcloud projects describe agencx --format='value(projectNumber)')/locations/global/workloadIdentityPools/github-pool/attribute.repository/Nikankhadka/agencx"
   ```

   Capture these two values for the GitHub secrets in Step 6:
   - Workload Identity Provider resource name (the full
     `projects/.../locations/global/workloadIdentityPools/github-pool/providers/github-provider`).
   - Service account email `github-deploy@agencx.iam.gserviceaccount.com`.

   The quick alternative to OIDC is a service-account JSON key stored as a
   GitHub secret (`GCP_SA_KEY`) - works, but OIDC is the repo's existing pattern
   (AWS uses it) and leaves no key to rotate.

## Step 3 - Vercel

1. Import the GitHub repo; Vercel auto-detects Next.js. Set the framework
   preset to Next.js and the **root directory to `frontend`**.
2. Vercel's native Git integration auto-deploys on every push to `main`. No
   deploy hook is needed; the `VERCEL_DEPLOY_HOOK_URL` path in `deploy.yml` can
   stay unused.

## Step 4 - API keys (all free)

- Google AI Studio key -> `LLM_API_KEY` (also reused for embeddings).
- Cohere key -> `COHERE_API_KEY` (rerank).
- Optional: Groq key (`LLM_FALLBACK_API_KEY`) and OpenRouter key
  (`LLM_FAILOVER_API_KEY`) for the two failover legs.
- Email: create a Resend or Brevo free account and capture the SMTP
  host/port/user/pass, or leave `EMAIL_PROVIDER=console` to log codes instead of
  sending (demo-only).

## Step 5 - Environment variables

Backend, as Cloud Run service env vars:

```
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

Frontend, as Vercel project env vars (all `NEXT_PUBLIC_`, inlined at build
time - set these before the first deploy):

```
NEXT_PUBLIC_API_URL=https://<service>.run.app
NEXT_PUBLIC_SUPABASE_URL=<...>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<...>
```

## Step 6 - GitHub Actions secrets

For `deploy.yml` (backend to Cloud Run):

```
GCP_PROJECT=agencx
GCP_REGION=us-central1
GCP_ARTIFACT_REPO=backend
GCP_WORKLOAD_IDENTITY_PROVIDER=<the full provider resource name from Step 2>
GCP_SERVICE_ACCOUNT=github-deploy@agencx.iam.gserviceaccount.com
```

## What the repo changes deliver

The founder steps above are external. The code changes that make them work live
in the repo and ship on a branch (`feat/deploy-gcp-vercel`):

1. `backend/app/llm/embedder.py` - a `GoogleEmbedder` (native
   `embedContent`, `outputDimensionality=384`) and a `'google'` branch in
   `get_embedder`.
2. `backend/app/shared/config.py` - `embedder` accepts `'google'`; new
   `google_embed_model` field.
3. `backend/app/main.py` - `_ALLOWED_ORIGIN_REGEX` widened to accept
   `*.vercel.app` and `*.run.app` (B-2 later narrows this to `*.agencx.app`).
4. `frontend/src/lib/tenant.ts` - the Vercel auto URL resolves to tenant-admin
   instead of being misread as a customer slug.
5. `.github/workflows/deploy.yml` - the backend job re-targets Cloud Run
   (build/push image to Artifact Registry, `deploy-cloudrun`, smoke test).
   The frontend stays on Vercel's Git integration.
6. `.env.example` files - document the new `EMBEDDER=google` / `RERANKER=cohere`
   / pooler `DATABASE_URL` settings.

`ci.yml` is unchanged and remains the gate (lint/typecheck/test/eval on every
push and PR). `deploy.yml` fires via `workflow_run` only after CI is green on
`main`, so a broken build can never reach production.

## Verifying

1. Locally: `make check` and `make ci` stay green.
2. Push a branch -> PR: `ci.yml` passes.
3. Merge to `main`: `deploy.yml` builds and pushes the image, deploys Cloud Run,
   and smoke-tests `<service>.run.app/health` (expect 200).
4. Vercel deploys `frontend` on merge; open `<project>.vercel.app` -> owner
   login -> onboarding -> go-live lands on Home.
5. A seeded tenant resolves:
   `curl https://<service>.run.app/api/public/tenant/bytefix` (expect 200). The
   customer chat page itself renders only once B-2 wires the wildcard domain.

## Caveats to keep in mind

- **Supabase free tier pauses after 7 days idle** (architecture section 13).
  Fine for a portfolio; keep it warm or move to Pro ($25/month) if it bites.
- **Free-tier LLM and embedding models train on your inputs** (section 13). No
  real customer data through the free tiers; swap provider before a real cohort.
- **Google's `thought_signature` 400** (known gap in `progress.md`) can reject
  multi-tool turns on the primary tier; it is a separate ticket, not a deploy
  concern, but may surface live.
- **B-2** (wildcard `*.agencx.app` plus the final CORS/BASE_HOSTS move) is the
  real domain launch; the `vercel.app`/`run.app` tweaks here are its temporary
  stand-ins.
