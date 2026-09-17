# Agencx - the canonical doc set

The build documentation for the **Agencx** product: a domain-agnostic,
multi-tenant SaaS where any small business self-onboards through a
conversation and gets a private, branded support-and-sales agent at
`agencx.app/{slug}`.

Start with [progress.md](progress.md) for Phase 1 scope, what is done,
and what is next. Paste [context-brief.md](context-brief.md) into AI
chat when planning work.

## The set at a glance

| Read this... | ...to answer |
|---|---|
| [progress.md](progress.md) | Where is the build? Phase 1 scope, done table, next list |
| [context-brief.md](context-brief.md) | What fits in one chat? Condensed Phase 1 brief |
| [prd.md](prd.md) | What is Agencx? Personas, scope, signals |
| [architecture.md](architecture.md) | How does it work? Invariants, seams, providers, eval gates |
| [history.md](history.md) | Where did this come from? The Wren story, once |
| [design/decisions.md](design/decisions.md) | Why was it built this way? Decision ledger D1 through D27 |
| [design/database.md](design/database.md) | The schema: tables, roles, RLS, migrations, seeds |
| [design/frontend.md](design/frontend.md) | The UI: design system, components, screens and states |
| [design/tokens.md](design/tokens.md) | The rhythm: spacing scale, type roles, layout recipes, CI guard |
| [design/api-contract.md](design/api-contract.md) | The API shape: Problem Details errors, safe SSE, review contract |
| [spec/](spec/README.md) | The tickets: user stories, acceptance criteria, done definitions |
| [research/owner-input-and-conversational-agent-architecture.md](research/owner-input-and-conversational-agent-architecture.md) | Which conversational pattern? Intent plus deterministic validation |
| [running.md](running.md) | How do I run it? Setup, logins, troubleshooting |
| [deploy.md](deploy.md) | How do I ship it? Vercel stack, founder steps, env vars, CI/CD |

## How to read the build

- Ticket status uses the six labels owned by [the spec index](spec/README.md):
  `Active - todo`, `Active - in progress`, `Active - PR open`,
  `Active - awaiting review`, `Done - merged`, `Deferred - Phase 2`.
- [design/conventions.md](design/conventions.md) binds all work.
  [The archive index](../archive/README.md) holds pre-Agencx material for
  provenance only.
