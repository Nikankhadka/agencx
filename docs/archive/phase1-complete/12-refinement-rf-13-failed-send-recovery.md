# 12 (RF-13): Failed-send recovery and draft preservation

**Status:** Done - merged in `0652b601436426d7dab171836df50f4bfd02e556` on 2026-10-03.
**Phase 1 area:** Refinement.

Delivered: a failed send recovers in place. The exact failed payload is
stored on the failed message and replayed once by an inline Retry in the
failed bubble, which reinstates that same bubble rather than appending a
duplicate customer bubble. The composer draft is held as the in-flight
payload on send and in `sessionStorage`, restored after a failure, and
cleared only on success; a newer draft typed after a failure survives a
retry. The in-stream `error` event is treated as a failed send, and a
handoff failure carries a working inline retry, so a failed bubble never
promises "Try again?" without a control. Nothing replays automatically. No
API or DB change.

## Agreed behavior

- **RF-13** - Failed sends recover in place with the exact failed payload and
  the draft preserved - explicit retry in the failed-bubble idiom, no unsafe
  automatic replay.

## Ticket detail

- **Visible outcome:** A failed send recovers in place: the failed bubble offers
  an explicit retry that replays the exact failed payload, and the draft
  survives the failure. Nothing replays automatically.
- **Current vs proposed:** Current: an error state and Retry exist in-session,
  but Retry replays the previous bubble rather than the failed payload
  (`CustomerChat.tsx` reads `messages[index - 1]?.text`), and the draft is
  cleared before send and not restored. Proposed: keep the draft in a slot
  cleared only on success, and retry the stored failed payload. Shipped:
  `CustomerChat` gives every bubble a stable id, stores a discriminated retry
  target on a failed bubble, replays it in place by id, holds the draft as the
  in-flight payload, and restores it on a fresh-send failure.
- **Design reference:** Shipped `frontend/src/app/[slug]/CustomerChat.tsx` send,
  error, and retry paths; `design/frontend.md` S1 and S3 `Error / disconnect`
  states (inline retry in the failed bubble).
- **Dependencies:** RF-12 (draft persistence), delivered in `87375d5`.
- **API/DB changes:** None.
- **Acceptance scenarios:** Force a network failure, confirm the draft stays in
  the composer and the failed bubble carries Retry; Retry sends the exact
  original text once; a success clears the draft; no automatic replay occurs.
- **Regression checks:** The `redraft` price-gate path and the existing
  error-state tests stay green.
- **OPEN:** Resolved. `OPEN: none`; the retry-target and draft-slot choices are
  recorded below.

## Decisions

- **Decision (2026-10-03):** The failed payload is stored on the failed message
  as a discriminated retry target (`{ kind: "send"; text } | { kind:
  "handoff" }`) and replayed once in place by a stable message id, not by
  reading a neighboring bubble and not by appending a duplicate customer
  bubble; an id that no longer exists no-ops.
- **Decision (2026-10-03):** The composer draft is held as the in-flight payload
  on send and in `sessionStorage`, cleared only on success, and restored on a
  fresh-send failure; a retry never clobbers a newer draft, clearing only when
  the stored draft still equals the completed payload.
- **Decision (2026-10-03):** The in-stream `error` event is a failed-send path
  too and stamps the same retry target with the same draft preservation; a
  handoff failure gets an inline Retry that re-runs the handoff, so the bubble
  never promises "Try again?" without a control.
- **Decision (2026-10-03):** Nothing replays automatically; retry fires only on
  the explicit control.

## Verification

- `make lint` - passed (contracts 3 kept, 0 broken, `check:tokens: OK`).
- `make typecheck` - passed (frontend tsc, backend mypy 225 files).
- `make format-check` - passed.
- `make test-frontend` - passed: 355 tests.
- Targeted E2E `rf-13-failed-send-recovery` - passed: 4.
- Regression E2E `rf-12-refresh-restore`, `typing-indicator`,
  `rf-11-ask-for-a-person` - passed: 13.
- Full `make test-e2e` - passed: 212, zero flaky.
- CI run 37106886289 on the branch - all green (backend, frontend, api-types,
  infra, security, e2e, eval-gate, Vercel). PR #74.
- Independent reviewer pass: SHIP on both passes; five minor findings fixed
  (stable id targeting, newer-draft preservation, handoff inline retry, status
  vocabulary, `sessionStorage` E2E assertions).
