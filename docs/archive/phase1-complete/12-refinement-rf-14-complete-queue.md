# 12 (RF-14): Complete-dataset queue filtering, searching, pagination, and attention counts

**Status:** Done - merged in `3d8ca7206fa40f78cea4a7765a86914e32d054c8` on 2026-10-03.
**Branch:** `feat/rf-14-complete-queue`.
**Phase 1 area:** Refinement.

Delivered: the owner's Chats queue filters, searches, and pages on the server
over the complete tenant dataset. `GET /api/conversations` answers an envelope
`{items, total, counts:{all,needs_you,unread,human}}`, with a `filter`
(`all` | `needs_you` | `unread` | `human`), a `q` search, and a derived
`handler` on every row. The screen opens on **Needs you** - an open escalation
or a conversation a human has taken over - with **All**, **Unread**, and **Human
handled** beside it, each carrying its count. Search matches a name, a
conversation reference, or an open escalation's summary across the whole
dataset, and "Load more" counts down against the server total. The console
Chats badge now shows the Needs you count, closing the RF-18 follow-up. No
migration: every new value is derived from `conversations.status`, the
escalations, and the RF-18 read marker, and every count is a query.

## Agreed behavior

- **RF-14** - Chats opens on **Needs you**, defined as an open escalation
  (`escalations.status <> 'resolved'`) or `conversations.status = 'human'`;
  All and Human handled are retained. One row per conversation (identity or
  conversation reference, attention reason, handler, waiting time) with
  attention counts beside the tabs; filtering, searching, and pagination apply
  to the complete dataset (verified past 200 conversations), and paging is
  "Load more" backed by a server total. Unanswered questions without a handoff
  stay in All unless an operational failure requires attention.

## Ticket detail

- **Visible outcome:** Chats opens on **Needs you** (an open escalation or
  `conversations.status = 'human'`); All and Human handled are retained. Rows
  carry identity or reference, attention reason, handler, and waiting time;
  attention counts sit beside the tabs; filter, search, and paging apply to the
  complete dataset with a server total behind "Load more".
- **Current vs proposed:** Current: tabs were All/Action needed/Unread with no
  Needs you or Human handled; there was no handler field; the client filtered
  the first 50 rows only (`chats/page.tsx`); there was no pagination; attention
  counts appeared only on the nav tab. Proposed: server-side filter, search, and
  paging with a total; a derived `handler` field; counts beside the tabs.
  Shipped: `GET /api/conversations` returns the envelope and the predicates;
  the Chats screen drives an infinite query keyed `[filter, q]` with a 300ms
  debounced search and a "Load more" button.
- **Design reference:** `agencx-prototype-v6.html` `renderScreen('chats')`
  `.chat-row` and filter row, `openChatsSearch()` / `filterChats()`;
  `design/frontend.md` S1 owner-surface paragraph. Shipped:
  `frontend/src/app/(tenant-admin)/(console)/chats/page.tsx`,
  `chats/lib/queue.ts`, `chats/lib/useConversationQueue.ts`,
  `home/lib/brief.ts`, and `components/ui/TabBar.tsx`.
- **Dependencies:** RF-1. Queue filtering precedes split-pane work (RF-15).
- **API/DB changes:** Extended `GET /api/conversations` with `q` (search), a
  `needs_you` / `unread` / `human` filter, and a response envelope
  `{items,total,counts}`; added a derived `handler` field to
  `ConversationSummary` from `conversations.status = 'human'`. No new column and
  no migration. Pagination keeps `limit`/`offset` and returns the total for
  "Load more".
- **Acceptance scenarios:** Seed 200 or more conversations including older
  unresolved issues beyond the first page; Needs you returns open escalations
  and human-handled threads; All returns everything; Human handled returns only
  `status = 'human'`; search matches a name or reference across the whole
  dataset, not the first page; "Load more" appends and stops at the total; the
  tab counts match the dataset.
- **Regression checks:** Tenant isolation on the conversations read; the
  existing Chats list and Home brief tests stay green.
- **OPEN:** Resolved. See Decisions.

## Decisions

- **Decision (2026-10-03):** **Unread is retained as a fourth tab.** The design
  authority documents All / Action needed / Unread, and RF-18 shipped unread as
  a separate axis with migration `0035`, the `unread` field, and
  `POST /api/conversations/{id}/read`; four chips fit the scrolling filter row,
  so the legacy tab survives alongside Needs you, All, and Human handled.
- **Decision (2026-10-03):** **Response envelope over `X-Total-Count`.** The
  list returns `{items,total,counts}` so the page, the "Load more" stop, and the
  tab counts arrive in one response; frontend and backend deploy as one Vercel
  project, so the shape ships atomically with no version skew.
- **Decision (2026-10-03, ADR D38):** **`needs_you` is an open escalation OR
  `status = 'human'`, and `handler` is derived from status.** The predicate,
  the count, and the page all run on the server where the whole dataset is
  visible; no new column is required because `conversations.status` already
  records who is replying.
- **Decision (2026-10-03):** **Counts respect `q` but not the filter**, so
  selecting a filter with no search yields `counts.<filter> == total` - the
  invariant the client's "Load more" relies on.
- **Decision (2026-10-03):** **The console Chats badge is reconciled off
  `needs_attention` onto the Needs you count**, closing the RF-18 follow-up; the
  badge and the queue now read the same server number.
- **Decision (2026-10-03):** **Handler and attention are independent axes**, so
  an escalated-then-taken-over row shows both the "You" handler label and the
  amber needs-you badge rather than one winning the trailing region.

## Verification

- `make dev` - stack up; `make migrate` - no pending migrations (no new
  migration).
- `make lint` - passed (backend ruff, import contracts 3 kept, 0 broken;
  frontend eslint, `check:tokens: OK`).
- `make typecheck` - passed (mypy 225 files, frontend tsc clean).
- `make test` - passed: backend 1275, frontend 365.
- `make build` - passed.
- `npm run gen:types -- --check` - `api-types.ts is up to date`.
- `make seed-tenant1 && make eval-skip-llm` - GATE PASSED (money guardrail,
  leakage 12/12 + 12/12, retrieval recall@3/5 1.000; generation, trajectory, and
  injection skipped with `--skip-llm`).
- `make seed` - demo world restored.
- `make test-e2e` - passed: 220, zero flaky.
- CI on PR #75 - all green: backend, frontend, api-types, infra, security, e2e,
  eval-gate, Vercel.
- Independent reviewer pass; findings fixed: the handler now survives on an
  escalated-then-taken-over row (both marks render), `frontend.md` S1 filter row
  updated to the shipped tabs, `getNextPageParam` sums loaded rows and the
  backend orders by `c.id desc` as a unique tiebreaker, a backend test covers
  the escalation-summary search branch, the E2E stub scopes its total to
  `filter` + `q`, the home-brief badge/panel invariant is one-directional, and
  the brief copy reads "N conversations need you.".
- PR [#75](https://github.com/Nikankhadka/agencx/pull/75).
