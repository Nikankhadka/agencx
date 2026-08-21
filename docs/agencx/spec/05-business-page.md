# Phase 1 - Business page (E)

The tenant surface re-cut: the two-tab console (Chat + Business) with advanced
Wren screens hidden, not deleted.

Tickets in this file:

- E-1: Tenant console -> Chat + Business
- E-2: Hide advanced screens, keep code

---

## E-1: Tenant console -> Chat + Business

### Summary

Re-cut the tenant console navigation to two tabs: Chat (onboarding
interview, then the everyday Copilot conversation) and Business (profile +
knowledge show-back, share link, enabled-tools section). The two-tab shell
is the whole tenant surface.

### Why

The PRD screen manifest (S1 + S2) and the ADR: the tenant app is not a
portal - it is a conversation plus the show-back surface. Wren's
seven-item sidebar (onboarding, knowledge, conversations, escalations,
pricing, dashboards, settings) is the wrong mental model for Sam.

### User stories

#### US-1 Two tabs, nothing else

**As** Sam,
**I want** my app to be Chat and Business,
**so that** everything I can do is in reach without navigating a tree.

- [ ] Sidebar (`lg+`) and bottom tab bar (mobile, D18): Chat + Business only
  (plus the tenant's brand/logo header)
- [ ] Chat hosts login-in-chat (until O-2 lands), onboarding, and the
  ongoing Copilot thread - one continuous thread (US: "the thread is the
  progress indicator")
- [ ] Business hosts the profile read-back, documents table, share link +
  QR, and the enabled-tools section (D-3)

#### US-2 Onboarding lands in the two-tab shell

**As** Sam finishing onboarding,
**I want** to land in Chat with the activation summary as the latest
message, Business showing my profile,
**so that** go-live feels like one conversation that became two tabs.

- [ ] Activation summary is a conversational message, not a card
- [ ] No celebration, no "complete your profile" CTA, no tour
- [ ] The onboarding thread persists as the canonical thread, scrollable

#### US-3 Mobile-first: bottom tab bar, not a drawer (D18)

**As** Sam on a phone,
**I want** the two tabs to render as an app-style bottom tab bar,
**so that** Chat and Business are always one thumb away and the known
narrow-mobile sidebar squeeze is gone.

- [ ] Below `lg`: Chat + Business render as a persistent bottom tab bar
  (icon + label, accent-container active pill, filled/outlined glyph idiom,
  ~64px height plus `env(safe-area-inset-bottom)`, minimum 44px touch
  targets)
- [ ] At `lg+`: the left sidebar stays (unchanged from the current shell)
- [ ] The hamburger drawer is no longer the tenant app's mobile nav (it stays
  available to the platform surface, E-3); brand header stays compact on
  mobile; sign-out is reachable, never hidden
- [ ] All states from the frontend spec (S1/S2 states) verified visually at
  375px and desktop

### Technical spec

- `frontend/src/app/(tenant-admin)/` nav model re-cut; routes behind hidden
  screens stay mounted (E-2 owns the hiding; E-1 owns the new nav)
- Mobile chrome: bottom tab bar in
  `frontend/src/app/(tenant-admin)/(console)/layout.tsx` below `lg`, sidebar at
  `lg+` (D18); token-only styling, no new visual language

### Tests

- E2E: two-tab nav, onboarding landing, 375px bottom tab bar (active state,
  safe-area padding, keyboard nav)
- Existing tenant-console tests updated to the new nav

### Files touched

- `frontend/src/app/(tenant-admin)/layout.tsx`, nav components
- `frontend/e2e/**`

### Definition of done

- [ ] Two tabs only
- [ ] Onboarding lands in the shell
- [ ] Bottom tab bar works at 375px (sidebar at `lg+`); e2e visual pass green

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

#### US-1 Tenant nav shows two tabs

**As** Sam,
**I want** conversations/dashboards/escalations/pricing out of my nav,
**so that** my app stays the two-tab shape.

- [ ] Sidebar renders Chat + Business only (E-1); advanced routes are
  unlinked
- [ ] Direct URL access to an advanced route by a tenant still serves (the
  screens exist) or 404s deliberately - the choice is: keep serving, they
  are just unlinked (decided here: keep serving; hiding is navigation-only)

#### US-2 Platform owner keeps visibility

**As** the platform owner,
**I want** the all-tenants view to still see conversation metrics, escalations,
and cost,
**so that** operations visibility survives the hide.

- [ ] Platform surface unchanged in this ticket (it never exposed the
  tenant's internal screens; its own aggregate views stay)

#### US-3 No dead code by stealth

**As** the maintainer,
**I want** the hidden screens' tests to keep running,
**so that** hidden is not a synonym for bit-rotted.

- [ ] The advanced screens' existing test coverage stays green and in CI
  (they still exist and must still work; F-1 handles genuinely dead code)

### Technical spec

- Nav config change only; no route deletion
- A code comment on the nav config marks the screens as "hidden until Stage
  2" (ponytail: the hiding is config, not deletion)

### Tests

- E2E: tenant nav shows two tabs; platform surface unchanged
- Advanced-screen tests still green

### Files touched

- `frontend/src/app/(tenant-admin)/` nav config
- `frontend/e2e/**`

### Definition of done

- [ ] Tenant nav hides advanced screens
- [ ] Advanced screens serve and stay tested
- [ ] Platform visibility unchanged
