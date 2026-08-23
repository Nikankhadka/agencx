# Phase 10 - Deployment (B)

Shipping the built product to a URL. Everything before this phase is proven in
containers on a laptop; this is the phase where the link an owner can hand out
becomes real.

Tickets in this file:

- B-4: Deploy as two containers behind one Vercel origin

---

## B-4: Deploy as two containers behind one Vercel origin

### Summary

Ship the frontend and the backend as two container services in a single Vercel
project, routed by `vercel.json`: `/api/*` and `/health` to the backend,
everything else to the frontend. One origin serves all three surfaces
(`/login`, `/{slug}`, `/admin`). The backend loses its local ML dependencies in
production and embeds through Google's hosted API instead, CI runs the backend
suite inside the image lineage that ships, and both workflows are pointed at the
branches this repo actually has.

### Why

The product promise is a link. Everything needed to serve it has been built and
proven locally since K-1, and the only thing standing between the build and a
reachable URL is the deploy itself.

The shape matters as much as the fact of it. Two services behind one origin
means the browser never makes a cross-origin request: no preflight, no CORS
allowlist to keep in step with a domain the founder has not bought yet, and no
second hosting provider whose free tier has its own idle-pause and its own
credentials. It also makes B-2 (the real domain) a single DNS record against a
single project rather than a coordination problem between two hosts.

### Design reference

None. This ticket has no screen - it is deliberate that the deploy changes
nothing a user can see.

### User stories

#### US-1 All three surfaces serve on one origin

**As** the founder,
**I want** the deployed project to serve the owner app, the customer page and
the platform console from one URL,
**so that** there is one address to hand out and one thing to keep alive.

- [ ] `vercel.json` declares a `frontend` and a `backend` service, each built
  from its own Dockerfile, with `/api/(.*)` and `/health` rewritten to the
  backend and `/(.*)` to the frontend
- [ ] `<project>.vercel.app`, `<project>.vercel.app/{slug}` and
  `<project>.vercel.app/admin` all serve
- [ ] The browser makes no cross-origin request in production;
  `_ALLOWED_ORIGIN_REGEX` covers local dev only, and says why

#### US-2 The production image stays lean, and still embeds

**As** the maintainer,
**I want** the shipping image to carry no torch or sentence-transformers,
**so that** the container starts fast and fits a small instance - without
quietly losing the ability to ingest knowledge.

- [ ] `EMBEDDER=google` selects a `GoogleEmbedder` that truncates server-side to
  `EMBEDDING_DIM` via `outputDimensionality`, so `knowledge_chunks.embedding`
  stays `vector(384)` with no migration and no re-ingest
- [ ] A response of the wrong width is refused with an actionable message rather
  than surfacing later as a Postgres type error at insert time
- [ ] Truncated vectors are renormalized, so hosted and local embeddings stay
  interchangeable for anything reading raw magnitudes
- [ ] The Google key is `LLM_API_KEY` reused, not a second credential to drift

#### US-3 An upload that will not fit says so

**As** an owner attaching a document,
**I want** an oversized file refused with a limit the app states,
**so that** I know what to change rather than hitting an opaque platform
failure.

- [ ] `MAX_UPLOAD_BYTES` sits under the platform's request-body limit, and a
  test pins that relationship rather than the number
- [ ] The 422 carries the backend's own wording; the size test derives from
  the constant, not a repeated literal

#### US-4 CI tests what actually ships

**As** the maintainer,
**I want** the backend suite to run inside the image's own `test` stage,
**so that** a test that secretly needs the local ML group fails in CI instead of
at deploy time.

- [ ] `backend/Dockerfile` has a `test` stage that adds only the `dev` group on
  top of the builder - still no `local-ml`
- [ ] `ci.yml`'s backend job runs pytest in that stage
- [ ] Lint, format, typecheck and the import contracts stay on the runner, where
  the dependency split is irrelevant and the cache is worth having

#### US-5 The pipeline points at branches that exist

**As** the maintainer,
**I want** CI and deploy triggered by this repo's real branches,
**so that** the pipeline runs at all.

- [ ] `ci.yml` runs on pushes to `staging` and `development`, and on every PR
- [ ] `deploy.yml` fires on CI success against `staging`, the production branch
- [ ] No workflow references `main`, which does not exist here

#### US-6 A deploy is verified, not assumed

**As** the founder,
**I want** a deploy to prove itself,
**so that** a green pipeline means the product is answering.

- [ ] After a production deploy, a smoke test hits `/health` and a seeded tenant
  lookup and fails loudly on either
- [ ] The job is gated on its secret existing, so the workflow no-ops with a
  notice until the founder wires it, exactly as it does today

### Technical spec

**The deploy target changed, and this ticket is where that is recorded.**
`architecture.md` names AWS ECS Fargate, and `deploy.md` named Google Cloud Run
before this ticket. Both are superseded by a single Vercel project running two
container services. The reasons, in order of weight: one provider instead of two
(one set of credentials, one idle-pause policy, one place to look when it is
down); same-origin serving, which removes the CORS surface entirely rather than
managing it; and a domain move (B-2) that becomes one DNS record against one
project. `infra/*.tf` and the `infra` CI job are **kept and dormant** - the
Terraform stack is real work and stays as evidence, validated on every PR so it
cannot rot silently, but nothing deploys through it.

- Both images are self-contained and are the artifact that ships;
  `Dockerfile.dev` files remain toolchain-only with deps in named volumes (K-1)
- `PORT` is not baked into either image: the host sets it, and the CMD falls
  back to the local compose port. Baking it would make the container listen
  where the host is not sending traffic
- The frontend builds with `output: "standalone"`; `public/` and `.next/static`
  are copied in beside the traced server, which does not gather them itself
- `NEXT_PUBLIC_API_URL` is empty in production on purpose: the callers read
  `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`, and `??` only
  falls back on null/undefined, so an empty string survives and every call
  becomes a same-origin `/api/...`
- Every direct dependency and base image is pinned exactly (`==`, full image
  tags), so a deploy builds what CI tested rather than whatever the range
  resolved to that morning

### Tests

- `backend/tests/test_google_embedder.py`: implementation selection by env, the
  dimension request, order preservation, the wrong-width refusal, empty input,
  API error propagation, and the zero-vector normalization guard
- `backend/tests/test_knowledge_api.py`: the cap is derived from the constant,
  the 422 carries the backend's own wording, and the cap is pinned under the
  platform limit
- `backend/tests/test_health.py`: the CORS allow/reject matrix over the narrowed
  regex
- `make ci` green; full Playwright suite green (71/71 at the K-1 merge)
- `docker build --target test` + pytest inside it, which is what CI now runs

### Files touched

- `vercel.json` (new), `frontend/Dockerfile` (new), `frontend/next.config.ts`
- `backend/Dockerfile`, `backend/Dockerfile.dev`, `frontend/Dockerfile.dev`
- `backend/app/llm/embedder.py`, `backend/app/shared/config.py`,
  `backend/app/main.py`, `backend/app/features/knowledge/api.py`
- `backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`,
  `frontend/package-lock.json`, `docker-compose.yml`
- `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`
- `backend/tests/test_google_embedder.py` (new), `backend/tests/test_knowledge_api.py`
- `docs/agencx/deploy.md`, `docs/agencx/progress.md`, `.env.example`

### Definition of done

- [ ] Three surfaces serve from one origin, no cross-origin request in prod
- [ ] Lean image embeds through Google at the schema's dimension
- [ ] CI runs the backend suite in the shipping image's `test` stage
- [ ] Both workflows fire on branches that exist
- [ ] A production deploy smoke-tests itself
