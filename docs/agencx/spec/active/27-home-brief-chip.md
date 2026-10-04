# 27: Home brief link target

**Status:** Active - in progress on `fix/27-home-brief-chip`.
**Phase 1 area:** Tenant console, Home.

Numbering note: 23 through 28 are the 2026-10 storefront and console
refinement batch; this is the fifth ticket in it.

## Design reference

`buildBrief` in
`frontend/src/app/(tenant-admin)/(console)/home/lib/brief.ts` and the
`BriefCard` chip that renders it; the share nudge is the
conversations-are-empty card.

## Summary

The "Get your link" chip on the Home brief (shown until the first customer
message) points at `/business/page`, the Business page screen with the public
link and its Copy and Share actions, instead of the `/business` hub.

## Why

The chip promises the link, and the hub only lists a row called "Business
page". The click should land where the link, Copy, and Share actually are
rather than one hop short of it.

## Current vs proposed behavior

| | Current | Proposed |
|---|---|---|
| Share-nudge chip target | `/business` (the hub's three rows) | `/business/page` (public link, Copy, Share) |
| Draft and queue chips | Their own destinations | Unchanged |

## Locked decisions

1. The target is `/business/page`, not the public `/{slug}`: the console page
   is where the owner copies and shares the link.
2. Only the share chip moves; the draft and queue chips keep their
   destinations.

## User stories

### US-1 One tap from the nudge to the link

**As** Sam with no customer messages yet,
**I want** the "Get your link" chip to open the page with the link,
**so that** sharing takes one tap, not two.

- [ ] The share chip href is `/business/page`
- [ ] The draft chip still points at the knowledge screen and the queue chip
      at Chats

## Technical spec

- `brief.ts`: the share item's chip href changes from `/business` to
  `/business/page`.
- No API, DB, or component change.

## Tests

- `home/lib/brief.test.ts`: the share-nudge assertion updates to
  `/business/page`.
- No e2e pins this chip target (checked: the `/business` waits in the tab
  and hub specs are tab navigation, unrelated).

## Files touched

- `frontend/src/app/(tenant-admin)/(console)/home/lib/brief.ts`
- `frontend/src/app/(tenant-admin)/(console)/home/lib/brief.test.ts`

## Definition of done

- [ ] The chip points at `/business/page`
- [ ] Unit tests, lint, and typecheck pass

## References

- E-4 Home and brief (archived) - the share nudge's origin
