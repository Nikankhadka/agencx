# 12 (RF-18): Owner read state in the chat queue

**Status:** Done - merged in `e1d5144` on 2026-10-02 (docs closeout `f25acef`;
branch `d672962`).
**Phase 1 area:** Refinement.

Delivered: real per-owner read state in the chat queue, with an unread row
emphasis, a working Unread filter, and an owner-authed mark-read endpoint.

## Agreed behavior

The owner's chat queue carries real per-owner read state: an unread row bolds
its title and shows a small accent dot, the Unread filter selects only
conversations with a customer message newer than the owner's read marker, and
opening a thread clears it. Unread and Action needed are separate axes and may
both be true. No double ticks.

Shipped: migration `0035_conversations_owner_read_at.sql` (plain column add,
RLS unchanged); unread computed in the list query as a `role = 'customer'`
message newer than `owner_read_at` (or a null marker), tenant-scoped;
`ConversationSummary.unread`; `POST /api/conversations/{id}/read` owner-authed,
tenant-scoped, `greatest(owner_read_at, now())` (idempotent, forward-only), 404
for foreign/missing; `ListRow` `unread` prop (accent dot + semibold title); a
real `Unread` filter; `/chats/[id]` marks read once per id and invalidates the
list query.

## Ticket detail

- **Visible outcome:** The owner's chat queue carries real per-owner read
  state: an unread row bolds its title and shows a small accent dot, the Unread
  filter selects only conversations with a customer message newer than the
  owner's read marker, and opening a thread clears it. Unread and Action needed
  are separate axes and may both be true. No double ticks.
- **Current vs proposed:** Current: `conversations` has no read marker; the
  Unread filter is a placeholder (`needs_attention || status = 'human'`) that
  conflates attention with read state, and opening a thread marks nothing.
  Proposed: add `conversations.owner_read_at` (migration `0035`), compute
  `unread` in the list query as a customer message newer than the marker,
  expose `POST /api/conversations/{id}/read` (idempotent, forward-only), and
  render the emphasis in the list.
- **Design reference:** `agencx-prototype-v6.html` `.chat-row` (name / time /
  status / preview); `design/frontend.md` section 7 S1 and the list-row recipe
  in section 4.4. Shipped: `frontend/src/app/(tenant-admin)/(console)/chats/`
  and `frontend/src/components/ui/ListRow.tsx`.
- **Dependencies:** RF-1 (the shared row grammar). RF-14 later moves the queue
  filtering and paging server-side; the read field rides the existing list
  response in the meantime.
- **API/DB changes:** Migration `0035_conversations_owner_read_at.sql` adds
  `conversations.owner_read_at timestamptz` (nullable; the existing RLS policies
  are unchanged). `ConversationSummary` gains `unread: bool`. New
  `POST /api/conversations/{id}/read` returns 204.
- **Acceptance scenarios:** A conversation with a customer message after the
  marker (or no marker) is unread; opening it marks it read and returning to the
  list shows it read; a later customer message makes it unread again; the Unread
  filter shows only unread rows; a second tenant cannot mark another's
  conversation read or see its unread state.
- **Regression checks:** `make lint`, `make typecheck`, `make test`,
  `make build`, and `make test-e2e`; the chats, tab-shell, and home-brief checks
  stay green.
- **OPEN:** none.

## Verification

- Backend `tests/test_conversations_api.py` - 21 passed.
- `make lint` - passed.
- `make typecheck` - passed.
- `make test` - 1233 backend + 278 frontend passed.
- `make build` - passed.
- `make test-e2e` - 165 passed.
- New `frontend/e2e/chats-read-state.spec.ts`.

## Known follow-up

- The console Chats tab badge remains `needs_attention`, not unread (switching
  it broke `home-brief.spec.ts`). Reconcile it in RF-14; it is recorded as an
  open item under RF-14 in `docs/agencx/spec/active/12-refinement.md`.
