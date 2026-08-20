# Agencx - the canonical doc set

The build documentation for the **Agencx** product: a domain-agnostic, multi-tenant
SaaS where any small business self-onboards through a conversation and gets a
private, branded AI support-and-sales agent at `{slug}.agencx.app`.

This set is the single source of truth. The pre-Agencx documentation is archived
under `docs/archive/` (indexed there) and is not maintained.

## The set at a glance

| Read this... | ...to answer |
|---|---|
| [`prd.md`](prd.md) | What is Agencx? Why does it exist? What is in Stage 1 scope, what is out, and what signals decide what happens next? |
| [`architecture.md`](architecture.md) | How does it work? Invariants, seams, agent flow, provider strategy, latency budget, eval gates |
| [`progress.md`](progress.md) | Where is the build right now? What is built, what is changing, what is new? |
| [`design/decisions.md`](design/decisions.md) | Why was it built this way? The decision ledger and ADRs, old and new |
| [`design/database.md`](design/database.md) | The schema: tables, roles, RLS, migrations, seeds |
| [`design/frontend.md`](design/frontend.md) | The UI: design system, tokens, components, the three screens and their states |
| [`spec/`](spec/) | The tickets: every piece of change work with detailed user stories, acceptance criteria, and done definitions |

## How to read the build

- `progress.md` is the one page to check for status. It marks every feature
  **BUILT** (with the commit evidence), **CHANGING** (built, and Agencx changes
  it - the change is described), or **NEW** (not built yet).
- The tickets in `spec/` are the work. Each ticket file declares its summary,
  why, detailed user stories, technical spec, tests, and definition of done.
- `conventions.md` (at repo root) binds all work; `docs/archive/` holds the
  pre-Agencx material for provenance only.

## Standing names

Agencx is the product name on every user-facing surface. The repository, the
database roles, and the environment variables keep the names they were built
with (`wren` roles, `wren_app` DB role, `WREN_APP_DB_PASSWORD`); renaming them is
deliberately out of scope - it is churn with no user value. Where docs reference
roles or modules by their old names, the name is the code name, not a branding
decision.