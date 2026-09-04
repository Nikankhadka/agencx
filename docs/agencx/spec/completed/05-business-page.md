# Phase 1 - Business page (E)

**Status: complete.**

The tenant surface re-cut: the three-tab app (Home + Chat + Business, D21) with
the advanced Wren screens hidden, not deleted.

Tickets in this file:

- E-1: Tenant console -> Home + Chats + Business (the shell)
- E-4: Home - the greeting and the brief
- E-5: Business hub + Booking page
- E-2: Hide advanced screens, keep code

Build order: E-1 -> E-4 -> E-5 -> E-2. E-1 delivers the chrome the other three
hang inside, so it goes first even though Home is the more interesting screen.

---

## E-1: Tenant console -> Home + Chats + Business

### Summary

Re-cut the tenant console navigation to three destinations: **Home** (the
owner's thread with the assistant, and what needs them), **Chats** (the
customers' threads, and stepping into one), **Business** (the show-back hub).
Bottom tab bar below `lg`, the same three items as the left sidebar at `lg+`.
This ticket is the chrome only - the screens it re-homes ship in E-4 and E-5.

### Why

The PRD screen manifest and D21. Wren's seven-item sidebar (onboarding,
knowledge, conversations, escalations, pricing, dashboards, settings) is the
wrong mental model for Sam. D18 replaced it with two tabs; D21 found the third
place hiding in the prototype - the home Copilot thread sits *underneath*
the prototype's tab bar with no tab of its own, and `navBack()` lights Chats
when you land on it. Naming Home makes it addressable.

### User stories

#### US-1 Three destinations, nothing else

**As** Sam,
**I want** my app to be Home, Chats and Business,
**so that** everything I can do is in reach without navigating a tree.

- [ ] Sidebar (`lg+`) and bottom tab bar (below `lg`) both render exactly:
  Home, Chats, Business - plus the tenant's brand/logo header on the sidebar
- [ ] Active item is the accent-container pill with the filled Material Symbol;
  inactive is quiet text with the outlined glyph (the idiom the shipped sidebar
  already uses)
- [ ] Sign-out stays reachable, never hidden behind a hamburger

#### US-2 Mobile-first: bottom tab bar, not a drawer (D18, D21)

**As** Sam on a phone,
**I want** the three tabs as an app-style bottom tab bar,
**so that** they are always one thumb away and the narrow-mobile sidebar
squeeze is gone.

- [ ] Below `lg`: persistent bottom tab bar, icon + label, ~64px height plus
  `env(safe-area-inset-bottom)`, minimum 44px touch targets
- [ ] At `lg+`: the left sidebar, same three items
- [ ] The hamburger Drawer is gone from the tenant console layout. `Drawer.tsx`
  itself stays - E-3's platform surface keeps it
- [ ] Content clears the bar: bottom padding equal to bar height plus the safe
  area, so no row and no composer sits behind it
- [ ] Verified visually at 375px and at desktop

#### US-3 Onboarding lands in the shell

**As** Sam finishing onboarding,
**I want** to land on Home with the activation summary as the latest message,
**so that** go-live feels like one conversation that became an app.

- [ ] `/onboarding` stays chrome-free - the prototype shows no nav at all until
  the business is live (`#phone.post`); `onboarding.completed` is that signal
- [ ] After completion the owner lands on `/home`
- [ ] Activation summary is a conversational message, not a card. No
  celebration, no "complete your profile" CTA, no tour
- [ ] The onboarding thread persists and stays scrollable

#### US-4 Existing screens re-homed

**As** Sam,
**I want** Chats and Settings to sit inside the app chrome,
**so that** they stop being chrome-free one-offs.

- [ ] `CHROME_FREE_PREFIXES` shrinks to `/onboarding`
- [ ] `/chats` and `/settings` render with the tab bar / sidebar under them
- [ ] Drill-down screens (`/chats/[id]`, `/settings/knowledge`) keep their
  `ScreenTopbar` back control - a thread and an edit surface are places you
  come back from, and the prototype pushes them as full screens

### Design reference

Build from the prototype, do not invent:
**`docs/agencx/design/prototypes/agencx-prototype-v6.html`**.

| Surface | Prototype anchor |
|---|---|
| Bottom tab bar | `#tabbar` / `.tab` / `.tab-lbl` / `#ndot`, and `#phone.post #tabbar{display:flex}` for the not-until-live rule |
| Full-screen push + back | `navTo()` / `navBack()` and the `.dst-topbar` each destination carries |

The prototype's bar has two tabs; D21 makes it three. Take the geometry,
states, and the active idiom from it - not the tab count.

Copy in the prototype is demo (Sababa reference tenant) - take structure,
states, spacing, and interaction vocabulary from it, not strings.

### Technical spec

- `frontend/src/app/(tenant-admin)/(console)/layout.tsx`: `NAV_ITEMS` becomes
  Home (`/home`), Chats (`/chats`), Business (`/business`). Reuse the existing
  item shape and active-state rendering; the sidebar arm is a re-cut, not a
  rewrite. Remove the mobile hamburger `<header>` and the `Drawer` usage
- New `frontend/src/components/ui/TabBar.tsx`, fed the same `NAV_ITEMS`
- Token-only styling. A new value lands in `theme.css` first, and a Tailwind
  class that is not a real token emits **nothing** silently (`bg-surface-hover`
  did exactly this in C-6) - validate every utility against `theme.css`
- Landing: `proxy.ts` keeps `/` -> `/login`. `/login` redirects an authed owner
  to `/home` when `onboarding.completed`, `/onboarding` otherwise. No auth
  logic goes into `proxy.ts` - the login page already owns that redirect
- Doc updates ship in this commit: `design/frontend.md` section 7 (the S0 Home
  surface spec, the app-chrome section from two tabs to three, the console
  shell paragraph) and `prd.md` (screen manifest gains S0; section 6 step 3)

### Tests

- E2E: three-tab nav and active state; 375px bottom tab bar with safe-area
  padding and keyboard nav; onboarding chrome-free before completion and
  landing on `/home` after; `/chats/[id]` and `/settings/knowledge` keep their
  back control
- Existing tenant-console tests updated to the new nav in the same commit

### Files touched

- `frontend/src/app/(tenant-admin)/(console)/layout.tsx`
- `frontend/src/components/ui/TabBar.tsx` (new)
- `frontend/src/app/(tenant-admin)/login/page.tsx` (post-login redirect)
- `frontend/src/styles/theme.css`, `frontend/e2e/**`
- `docs/agencx/design/frontend.md`, `docs/agencx/prd.md`

### Definition of done

- [ ] Three destinations, sidebar and tab bar
- [ ] Bottom tab bar works at 375px, sidebar at `lg+`, nothing behind the bar
- [ ] Onboarding chrome-free, lands on Home
- [ ] The `progress.md` "console sidebar squeeze below ~375px" gap is closed
- [ ] `make check` green, e2e visual pass green

---

## E-4: Home - the greeting and the brief

### Summary

Build Home: the owner's own thread with the assistant, headed by a greeting,
carrying **the brief** - the small set of things that want the owner right now,
each as a card with the one action that resolves it. Ported from the
prototype's morning brief, fed by the state that exists in Stage 1.

### Why

"Important stuff the owner wants to see the moment they open the app" is the
point of a home screen, and it is what the prototype's `showMorningBrief()`
does. In Stage 1 the honest items are narrow but real: a customer the assistant
could not finish with, a knowledge draft that is answering nothing until it is
saved, a business that has not shared its link yet. Each one is a thing left
undone by someone else's design, surfaced before it rots.

The prototype's brief is full of Stage 2 material - jobs, an overdue balance, a
payment reminder. That data does not exist yet, and a card with nothing behind
it is the dead surface the PRD forbids. So the **implementation** ports now and
the **item kinds** are only the ones backed by real state; Stage 2's quote and
order approvals arrive as new kinds in the same list, not as new screens.

### User stories

#### US-1 What needs me, the moment I open the app

**As** Sam,
**I want** the things waiting on me at the top of Home,
**so that** I do not have to go looking for them.

- [ ] Greeting heads the screen (`Good morning, <name>.`), from the O-1 profile
- [ ] Brief items render as cards under it: headline, action chip(s), one
  context note line
- [ ] Each chip lands on the screen that resolves the item
- [ ] Stage 1 item kinds, each rendered only when its state is real:
  1. **Customers waiting on you** - `/api/conversations` rows with
     `needs_attention`. Note line is the assistant's `pending_summary`. Chip:
     Open -> `/chats` filtered to Action needed (or the thread, when it is one)
  2. **Knowledge waiting to be saved** - `/api/knowledge/records` rows with
     `status === "draft"`. A draft answers nothing until saved (D19). Chip:
     Review -> `/settings/knowledge`
  3. **Not shared yet** - until the public page has been opened once. Chip: Get
     the link -> the Booking page (E-5)
- [ ] No metric tiles, no dashboard, no charts

#### US-2 Nothing waiting is a quiet screen

**As** Sam with nothing outstanding,
**I want** Home to just be my thread,
**so that** the app is not congratulating me for a normal morning.

- [ ] No items -> no cards. The greeting and the thread, nothing else
- [ ] Never a "you're all caught up" card - absence is the message

#### US-3 Home is a conversation, not a dashboard

**As** Sam,
**I want** to type to the assistant from Home,
**so that** the everyday relationship stays a conversation (S1).

- [ ] The command pill sits at the bottom of Home, as it does on `/onboarding`
- [ ] The thread scrolls; the brief cards are part of it, at the top
- [ ] Assistant turns are paced the way the thread already paces them
  (typing indicator, then the reveal) - static content is never re-paced on a
  restored view

#### US-4 The Chats tab says when someone is waiting

**As** Sam looking at any tab,
**I want** to see that a customer needs me,
**so that** the signal does not depend on my being on Home.

- [ ] The Chats tab carries an unread dot when any conversation has
  `needs_attention` (the prototype's `#ndot`)

### Design reference

**`docs/agencx/design/prototypes/agencx-prototype-v6.html`**.

| Element | Prototype anchor |
|---|---|
| Greeting | `#greeting` / `#greeting-h1` |
| The brief | `showMorningBrief()` - the agent line, then the cards |
| Brief card | `addCard(hl, chips, note)` -> `.a-card` / `.a-hl` / `.a-chips` / `.a-chip` / `.ctx-note` |
| Thread paced turns | `agentMsg()` - typing indicator, then reveal |
| Composer | `buildCmdPill()` |
| Tab unread dot | `#ndot` |
| Approval interaction (Stage 2) | `showReminderHitl()` -> `.care-draft` with Send it / Edit in `#co-overlay` |

**Do not port `addJobRows()`** - jobs are Stage 2 and there is no data behind
them.

**Do not build the approval overlay in this ticket.** Every Stage 1 chip is a
navigation, not an approval; an editable-draft overlay with nothing to approve
is a dead surface. It ports with the first Stage 2 kind that needs it, from the
anchor named above.

### Technical spec

- New `frontend/src/app/(tenant-admin)/(console)/home/page.tsx` plus
  `home/components/` for the card. Reuse `Thread.tsx` primitives,
  `CommandPill`, `ThinkingDots`, `StreamingText` - Home is the onboarding
  thread's idiom continued, **not** `ChatBubble` (that is the operator thread,
  C-6)
- **Item shape** (the seam Stage 2 extends):
  `{ kind, headline, note, chips: { label, href }[] }`
- **Data: no new backend route.** Compose from the two endpoints that already
  serve this state, via `useApiQuery`: `/api/conversations` (already the source
  of the Chats "Action needed" filter) and `/api/knowledge/records`
- Mark the composition with a `ponytail:` comment naming the ceiling: when
  Stage 2 adds quote-approval and order-approval kinds, promote to a single
  `/api/brief` returning a typed item list. The card component and the item
  shape are already that contract, so the promotion is server-side only

### Tests

- Unit: the item-composition function - one kind each, several of one kind, no
  kinds; a draft document produces exactly one item regardless of section count
- E2E: seeded `needs_attention` conversation and seeded unsaved draft produce
  exactly two cards, each chip landing on the right screen; neither seeded
  produces no cards and no empty-state card; the Chats tab dot appears and
  clears

### Files touched

- `frontend/src/app/(tenant-admin)/(console)/home/**` (new)
- `frontend/src/components/ui/TabBar.tsx` (the unread dot)
- `frontend/src/styles/theme.css`, `frontend/e2e/**`

### Definition of done

- [ ] Greeting, brief cards, thread, composer - at 375px and desktop
- [ ] Three item kinds, each only when real; nothing waiting renders no cards
- [ ] No new backend endpoint; the `ponytail:` upgrade path is written down
- [ ] `make check` green, e2e green

---

## E-5: Business hub + Booking page

### Summary

Build the Business tab: a hub of rows, and the Booking page behind one of them
- the profile show-back, the public link with a copy control, and the QR.

### Why

The Business tab is the show-back surface: what the assistant believes about
the business, and how customers reach it. The hub shape is what lets Stage 2
add Schedule, Money and Plan without re-cutting navigation - a row is cheaper
than a tab, and the prototype already renders it that way.

### User stories

#### US-1 A hub of real rows

**As** Sam,
**I want** Business to be a short list of places,
**so that** I can find the one thing I came for.

- [x] Rows in Stage 1: **Booking page** and **Settings**. Nothing else
- [x] Schedule, Money and Plan are **absent**, not disabled (E-2, PRD "never
  build dead surfaces")

#### US-2 The booking page shows what customers see

**As** Sam,
**I want** to see my business as a customer finds it, and get the link,
**so that** I can share it and trust what it says.

- [x] Profile show-back from the O-1 interview profile
  (`tenant_config.config->profile`): business name, what it does, hours
- [x] The public URL with a Copy control
- [-] A QR for the same URL - **built, then removed by E-6.** It was never in
  the prototype's owner screen, nothing used it, and it carried a dependency
  (`qrcode-generator`) for that. Sharing is `navigator.share()` with a
  clipboard fallback
- [-] Live / not-live state is legible - **void.** The bullet was written
  against an assumption that does not hold: there is no not-live state to
  render. `tenants.status` defaults to `'active'` (migration 0003) and
  self-signup inserts `'active'` outright
  (`features/tenants/service.py:63`); onboarding confirm never touches it. A
  badge reading that column would say "Live" throughout the interview, which
  is worse than showing nothing. What "live" means for a self-onboarded tenant
  is `config->onboarding.completed`, and by the time the owner can reach this
  screen it is already true. `tenants.status` is a platform-admin lifecycle
  (its only writer is the suspend control, its only reader the customer page),
  not an owner-facing one

### Design reference

**`docs/agencx/design/prototypes/agencx-prototype-v6.html`**:
`renderScreen('business')` for the hub (`.bh-row`: icon, label, chevron) and
`renderScreen('booking')` for the booking page (name, tagline, "How leads come
in", `.bk-link-pill` with Copy, the platform buttons).

The shipped `/settings` page (`settings/page.tsx`) is already this hub idiom
built from the same anchor, with the same "one row, no dead rows" call - reuse
`RowLink` and `ScreenTopbar` exactly as it does.

### Technical spec

- New `(console)/business/page.tsx` (the hub) and
  `(console)/business/booking/page.tsx`
- **The QR has no implementation in the repo** (nothing matches
  `qrcode`/`QRCode`). Render it as inline SVG generated from the slug URL
  rather than adding a dependency; if that proves fiddly, flag it rather than
  pulling in a package silently
- The enabled-tools section does **not** ship here - that is D-3, deferred
- The prototype's cover-photo affordance does not ship - there is no upload
  behind it

### Tests

- E2E: hub shows exactly two rows; booking page renders the seeded tenant's
  profile, the copy control puts the public URL on the clipboard, the QR
  renders

### Files touched

- `frontend/src/app/(tenant-admin)/(console)/business/**` (new)
- `frontend/src/styles/theme.css`, `frontend/e2e/**`

### Definition of done

- [x] Two hub rows, no dead rows
- [x] Booking page shows the profile and the link (the QR is gone - see US-2)
- [x] `make check` green, e2e green

---

## E-2: Hide advanced screens, keep code

### Summary

Remove the advanced Wren screens (conversations + traces, dashboards,
escalations queue, pricing editor) from the tenant navigation while keeping
their routes, code, and platform-owner access intact. Hidden, not deleted.

### Why

The merge decision: "Advanced screens hidden, not deleted." Stage 2 will
re-land these surfaces with a purpose; deleting them would throw away the
working machinery and its tests. Hiding keeps the tenant app honest today
without re-building tomorrow.

### User stories

#### US-1 Tenant nav shows three destinations

**As** Sam,
**I want** conversations/dashboards/escalations/pricing out of my nav,
**so that** my app stays the three-destination shape.

- [ ] Sidebar and tab bar render Home + Chats + Business only (E-1); advanced
  routes are unlinked
- [ ] Direct URL access to an advanced route by a tenant still serves - the
  decision here is: keep serving, hiding is navigation-only

#### US-2 Platform owner keeps visibility

**As** the platform owner,
**I want** the all-tenants view to still see conversation metrics, escalations,
and cost,
**so that** operations visibility survives the hide.

- [ ] Platform surface unchanged in this ticket (it never exposed the tenant's
  internal screens; its own aggregate views stay)

#### US-3 No dead code by stealth

**As** the maintainer,
**I want** the hidden screens' tests to keep running,
**so that** hidden is not a synonym for bit-rotted.

- [ ] The advanced screens' existing test coverage stays green and in CI (they
  still exist and must still work; F-1 handles genuinely dead code)

### Design reference

**`docs/agencx/design/prototypes/agencx-prototype-v6.html`**,
`renderScreen('business')`: the hub rows that stay in Stage 1 are **Booking
page** and **Settings** (E-5 builds them). **Schedule**, **Money**, and
**Plan** are the Stage 2 rows this ticket keeps out - they exist in the
prototype so the hub's shape is right, not because Phase 1 ships them.

### Technical spec

- Nav config change only; no route deletion. E-1 already leaves them unlinked,
  so this ticket is the comment that says why, plus the test that holds it
- A code comment on the nav config marks the screens as "hidden until Stage 2"
  (ponytail: the hiding is config, not deletion)

### Tests

- E2E: tenant nav shows three destinations and none of the advanced ones;
  an advanced route still serves when typed directly; platform surface
  unchanged
- Advanced-screen tests still green

### Files touched

- `frontend/src/app/(tenant-admin)/(console)/layout.tsx` (the comment)
- `frontend/e2e/**`

### Definition of done

- [ ] Tenant nav hides advanced screens
- [ ] Advanced screens serve and stay tested
- [ ] Platform visibility unchanged


---

## E-6: The Booking page as the customer's view

**Amendment** - recorded after the work shipped (founder walkthrough,
2026-08-23). Shape per `README.md`.

### Summary

Finish the Booking page against the prototype: the cover photo, the Services
list and the platform tiles that E-5 left out. Remove the QR and do not add a
"Get a quote" CTA.

### Why

E-5 left three parts out as "dead surface", each because nothing stood behind
them. Two of those reasons no longer hold, and the third was a scope call the
founder has now made differently:

- the cover photo was blocked on "images are refused (O-3)" - but that ruling is
  about *knowledge*, and a brand asset is not knowledge;
- the platform tiles were blocked on "no integrations" - they are link slots,
  not integrations;
- the Services list was blocked on quoting being off - but the rows come from
  the owner's own saved material, not from the quoting engine.

The QR goes the other way: E-5 added it, it was never in the prototype's owner
screen, and the founder does not use it.

### User stories

#### US-1 A cover photo

- [x] `.bk-photo-wrap`: 200px, tinted invitation while empty, the photo once set,
  "Edit photo" pill in the corner
- [x] Migration 0021 `tenant_assets` holds the bytes in Postgres, with a
  `ponytail:` note naming object storage as the upgrade path
- [x] Resized on a `<canvas>` before upload; 2MB server cap as the backstop
- [x] Served behind the owner's session, so the page fetches it and hands an
  object URL to the `<img>` - a bearer token cannot ride on `src`

#### US-2 Services, without a model near a price

- [x] Rows derived from the "What we offer" and "Prices" sections of the owner's
  **saved** knowledge; a draft they have not reviewed is not published
- [x] A price is a verbatim slice of the owner's own line, cut at the index the
  pricing gate's extractor reports - the money rule held by construction
- [x] Absent entirely when there is nothing saved; no empty heading

#### US-3 The platform tiles are link slots

- [x] Empty is dashed and reads "Add"; filled is solid and reads "Open"
- [x] Tapping opens a panel and never navigates on the tap itself - navigating
  left no way back to a link already saved
- [x] Stored in `tenant_config.brand->links`; schemes allowlisted server side

#### US-4 What does not ship

- [x] The QR, and the `qrcode-generator` dependency with it
- [x] The "Get a quote" CTA (quoting is a Stage 2 opt-in)
- [x] Sharing is `navigator.share()` with a clipboard fallback, not the
  prototype's hardcoded four-icon sheet

### Known gap, deliberately left

The page a customer lands on (`(customer)/page.tsx`) is still a bare chat
surface with none of this. The Booking page is the owner's preview of a
storefront that has not been built. Porting
`docs/archive/prototypes/agencx-storefront-customer-v3.html` is the next ticket, and until it lands the
headings here claim only what is true.

**E-5's "live / not-live state is legible" DoD bullet was never implemented** -
nothing on the page reads `tenants.status`. E-6 did not add it either. It wants
its own ticket rather than another silent carry-forward.

### Definition of done

- [x] `make check`, `check:tokens`, `make test-e2e` green
- [x] Side by side against the prototype at 390px
