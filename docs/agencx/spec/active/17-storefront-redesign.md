# 17 - Storefront redesign: no-image-first base, Uber Eats-style mature state (M-7)

**Status:** built on `feat/m7-storefront-redesign` (M-7 US-1 through US-6);
founder review amendments applied (hero veil in both states, long facts wrap);
awaiting merge. Prototype
[`agencx-storefront-customer-v4.html`](../design/prototypes/agencx-storefront-customer-v4.html)
approved in founder review.

Founder request: the customer storefront at `/{slug}` reads unfinished for a
business with no photos. The hero reserves a `min-h-36` band for a cover that
never comes, every offering row holds a 144px media slot that stays empty,
and the only chat entry is a 44px header icon. Rebuild it no-image-first:
the no-photo state is the base foundation, tenants with media mature into an
Uber Eats-style state of the same composition, and one persistent chat entry
serves the whole page.

## Design reference

`docs/agencx/design/prototypes/agencx-storefront-customer-v4.html`, frozen
from the reviewed `.lavish/storefront-redesign.html`. Today screenshots,
edge cases, and the full decision record live inside the artifact. Port
structure, states, and vocabulary from it; take behaviour, never strings,
except where the artifact's words specify a state (no "nothing published"
notice); visual values are `theme.css` tokens only, no new tokens.

Review decisions (hero fallback amended in founder review 2026-09-17):

- Hero fallback: **the veil in both states** (supersedes A. Plain identity) -
  with no cover a 96px `--gradient-veil` band stands where the cover would be;
  with a cover the same veil lies over the photo's lower edge. The monogram
  overlaps the band identically in both states, so media changes the band
  filling, never the composition.
- Long profile facts wrap to multiple lines and are never clipped or
  ellipsized (restores the v4 edge case).
- Offering layout: single-column rows on mobile, two-column grid at `sm+`
  (today's responsive behavior with compact rows and no reserved media
  space).
- Profile facts: `business_type` chip + `hours` fact + `services` subtitle;
  `contact` stays private. The legacy combined `tagline` stays in the
  payload but is no longer the rendered subtitle.
- US-6 revised in review: the fixed bottom Ask bar is gone. The single
  persistent header chat button is the only entry, and the header identity
  taps back to top.

## Scope

- Must: M-7 US-1 and US-3 through US-6 as reviewed, the backend payload
  addition, and E2E pins plus the new mobile spec. Tokens only, no new
  dependencies.
- Should: stretched profile strings wrap to multiple lines, never clipped
  (v4 edge case).
- Could: nothing reserved; video offerings keep today's poster and badge
  behavior unchanged.

## M-7 US-1: no-image base composition

- Veil hero: veil band in the cover's place (or over the photo's lower edge
  when one exists), monogram overlap in both states, name, services subtitle,
  `business_type` chip, `hours` fact. No reserved row media slots.
- Minimal business (no offerings, with or without cover): name, brief
  description, facts, and the assistant-invitation panel using the full page
  - hero top, invitation middle, footer bottom. Never a "nothing published"
  notice. The sakura wash lives only behind the assistant's card, never the
  hero.
- Null prices render no price line in rows and sheets; zero categories fold
  into "More"; one offering with no category renders one "What we offer"
  section with no nav.

### Acceptance signal

- [ ] Sababa with no photos: hero carries the veil band rather than an empty
  cover slot, rows carry no dead media space, type chip and hours fact render
  from the payload.
- [ ] Empty tenant: full-page minimal state with invitation and Reply pill,
  footer pinned to the bottom, no "nothing published" copy.
- [ ] Null-price and no-category states from the v4 edge cases render as
  specified.

## M-7 US-2: spec and docs (this ticket)

- The redesign is carried in the docs so future tickets build on it instead
  of around it: this ticket, the `progress.md` row, the `spec/README.md`
  active row and Building-UI line, the `frontend.md` S3 and prototype
  paragraphs, and the `conventions.md` prototype pointer.
- No component work; the ticket file itself is the deliverable.

### Acceptance signal

- [ ] Every pointer above names v4; no active doc still presents v3 as the
  storefront reference.

## M-7 US-3: category navigation

- Sticky category nav with scrollspy on mobile; tap scrolls to the section.
- Desktop keeps the Uber Eats geometry: sticky left Browse sidebar while
  the menu scrolls.

### Acceptance signal

- [ ] Scrolling the menu moves the active nav state; tapping a category
  scrolls to its section on mobile and desktop.

## M-7 US-4: media maturity

- Optional cover with the veil over its lower edge and monogram overlap; 96px
  thumbnails only where media exists; broken-image tile fallback; video keeps
  today's poster and badge behavior.
- The v4 demo photos are Wikimedia Commons stand-ins for the mature state
  and never ship.

### Acceptance signal

- [ ] Photos-on Sababa matches the v4 mature frames; a broken image renders
  the fallback tile with no layout shift.

## M-7 US-5: detail sheet

- Tightened sheet: photo when present, no empty media box otherwise. "Ask
  about this" seeds the composer exactly as today.
- Deterministic pricing untouched: the sheet renders the owner's published
  price only; no model-produced amount anywhere.

### Acceptance signal

- [ ] Sheet with and without media matches v4 frames 3a/3b; "Ask about
  this" seeds the composer with the item context.

## M-7 US-6: single chat entry

- One persistent header chat button; no fixed bottom Ask bar; header
  identity taps back to top; share kept. Chat internals, quoting, and order
  lookup untouched.

### Acceptance signal

- [ ] No fixed bottom bar on the storefront at any viewport; the header
  button opens the sheet; tapping the header identity returns to top.

## Backend: profile facts in the public payload

- Extend the public storefront response (service `read_public_storefront`)
  with `business_type`, `hours`, and `services` from
  `tenant_config.profile`. `contact` is excluded by design; publishing it
  would need its own ticket.

### Acceptance signal

- [ ] Unit tests pin the three new fields and the absence of `contact` on
  the public response.

## Tests

- Backend unit tests for the payload addition.
- `storefront.spec.ts` pins updated for the new composition; new mobile
  spec covering the no-photo base and the minimal business state.
- `make check`, `make eval-skip-llm`, and the full E2E suite per the
  verification phase.

## Definition of done

- [ ] All six stories meet their acceptance signals.
- [ ] `make lint`, `make typecheck`, `make test`, `make eval-skip-llm`
  green; E2E suite green including the new mobile spec.
- [ ] Founder walkthrough of `/{slug}` on mobile and desktop against v4.
- [ ] One commit on `feat/m7-storefront-redesign`, PR to `development`.
