# History: Wren to Agencx

This is the one place the Wren origin story lives. Other docs link here
instead of retelling it.

## What Wren proved

Wren was the shipped build this product re-scopes: grounded answers from
owner material, cross-tenant isolation in the database, a deterministic
money boundary, and a generalization proof (a second vertical onboarded by
config alone). Measured baselines are recorded in
[architecture.md](architecture.md) and the frozen evidence stays in
[the archive index](../archive/README.md).

## Why Agencx re-scoped it

Agencx keeps the machinery and narrows the surface: owner self-onboards in
a chat, lands in a three-tab app (Home, Chats, Business), uploads
knowledge, and an anonymous customer asks questions at `/{slug}` grounded
in that material. Quoting, recommendations, payments, scheduling, and
related machinery stay built but off by default behind per-tenant opt-ins.

## Standing names

The repo, database roles, and env vars keep the names they were built
with. Renaming them is churn with no user value.

| Name | What it is |
|---|---|
| `wren_app` | Database role used by the app connection |
| `wren_resolver` | Owner of `resolve_tenant_slug()`, the single audited RLS bypass |
| `WREN_APP_DB_PASSWORD` | Env var holding the `wren_app` password |
| `x-wren-surface`, `x-wren-slug` | Retired request headers, replaced by paths |

## Where the old docs live

Pre-Agencx material is frozen for provenance only in
[the archive index](../archive/README.md). Nothing there is maintained.
