# 24: Desktop overlay standard

**Status:** Done - merged in `c85e96f` on 2026-10-05.
**Phase 1 area:** Tenant console and storefront UI.

Numbering note: 23 through 28 are the 2026-10 storefront and console
refinement batch; this is the second ticket in it. 22 is the production
hardening umbrella.

## Design reference

The `Sheet` and `Modal` primitives (`frontend/src/components/ui/Sheet.tsx`,
`frontend/src/components/ui/Modal.tsx`) and every render function that mounts
one: `ReviewDocument`
(`frontend/src/components/knowledge/ReviewSheet.tsx`), `ProfileFieldSheet`,
`ContactSheet`, `AbnSheet`, `ServicesSheet`, `VoiceSheet` (all under
`frontend/src/app/(tenant-admin)/(console)/business/details/components/`), the
offering-detail `Sheet` and the RF-7 editor block in `Storefront`
(`frontend/src/app/[slug]/Storefront.tsx`), and the offering and category
`Modal`s in
`frontend/src/app/(tenant-admin)/(console)/business/components/OfferingsList.tsx`.
Prototype block: `#sheet-settings-edit` and `.bottom-sheet` in
`design/prototypes/agencx-prototype-v6.html`. The `lg` boundary is the
app-wide desktop boundary (`DESKTOP_QUERY`,
`frontend/src/lib/useMediaQuery.ts`); `design/frontend.md` section 4.6 gains
the `--width-doc` token entry.

## Summary

At `lg+` (1024px and up) every sheet becomes a centered, height-capped dialog
instead of a full-width bottom pull-up: form sheets cap at `max-w-md`, document
surfaces at 768px through a new `--width-doc` token. Below `lg` every sheet
keeps today's bottom pull-up, handle, scrim, slide-up, and focus management.
`Modal` gains height containment with an internal scroll area, so a tall
offering editor scrolls inside the panel instead of exceeding the viewport.
The customer chat panel (`CustomerChatPanel`) is a separate, deliberately
bespoke overlay and does not change.

## Why

The owner edits on a desktop browser, and today the edit sheet arrives as a
full-width pull-up that covers most of the screen and runs up to 85% of the
viewport height. The same gesture is correct on a phone, where the sheet is
the whole interaction, and wrong on a desktop, where the owner expects to
change one field without losing the page. The `desktop` opt-in that already
exists on `Sheet` proves the intent but is wired to only one caller; the two
primitives also disagree on height (`Sheet` caps, `Modal` does not) and on
boundary (`sm` versus the app's `lg`). One standard, applied at the primitive,
removes the per-caller drift.

## Current vs proposed behavior

| | Current | Proposed |
|---|---|---|
| Sheet at 640-1023px | Knowledge review is a centered dialog at 640px+; all other sheets are bottom pull-ups | Every sheet is a bottom pull-up below 1024px |
| Sheet at 1024px+ | Knowledge review centered at 48rem; every other sheet full-width bottom pull-up up to 85% viewport height | Every sheet centered and height-capped: forms `max-w-md`, documents `--width-doc` (768px) |
| Sheet closed state at desktop | `sm:translate-y-[calc(100vh_-_2rem)]` for the review sheet only | The same full-viewport clear applies at `lg` to every sheet |
| Modal with tall content | Panel has no max height; the offering editor can exceed the viewport | Panel caps at `calc(100vh-2rem)`; the body scrolls, the title stays fixed |
| Customer chat panel | Docked panel at `lg+`, full-height sheet below | Unchanged |

## Locked decisions

1. `lg` (1024px) is the only desktop boundary for overlays. The `sm` switch
   and the one-caller `desktop` boolean are retired.
2. Width follows content: `variant="form"` (default) caps at `max-w-md`;
   `variant="document"` caps at `--width-doc` (768px). `ReviewSheet` and the
   storefront offering-detail sheet are the document callers; every form
   caller uses the default.
3. Below `lg` nothing about a sheet changes.
4. `Modal`'s panel is `max-h-[calc(100vh-2rem)]` with a fixed title and a
   `min-h-0 flex-1 overflow-y-auto` body. `ConfirmDialog` shares the fix and
   keeps its `layer="top"` behavior.
5. `CustomerChatPanel` is out of scope and keeps its RF-8 presentation.
6. `--width-doc: 768px` is a plain `:root` variable in `theme.css` used
   through the custom-property shorthand (`lg:max-w-(--width-doc)`), the
   RF-8/RF-15 pattern that needs no `make dev-reset`; `design/frontend.md`
   4.6 records it.

## User stories

### US-1 Editing on a desktop no longer takes over the screen

**As** Sam editing one field from the console or the storefront preview,
**I want** the editor to arrive as a compact centered dialog over the page,
**so that** the change feels like a change, not a mode switch.

- [ ] At 1280px a form sheet (Edit ABN and tax, Edit contact, Edit services,
      Edit voice, Edit name/hours/description) renders centered at 448px or
      less and is shorter than the viewport
- [ ] At 1280px the knowledge review and the storefront offering detail render
      centered at 768px or less, shorter than the viewport
- [ ] Scrim click, Escape, focus trap, and focus restoration behave as today

### US-2 Mobile keeps its sheet

**As** Sam on a phone,
**I want** the same editors to slide up from the bottom as they do now,
**so that** nothing about the mobile interaction is relearned.

- [ ] At 390px a form sheet touches the bottom edge and spans the viewport
      width with the handle, rounded top, and scrim
- [ ] The 640-1023px range keeps the bottom pull-up for every sheet

### US-3 A tall editor scrolls inside its panel

**As** Sam editing an offering with media,
**I want** the dialog to stay within the viewport and scroll its body,
**so that** the Save action is always reachable.

- [ ] At a short viewport a Modal body taller than the panel scrolls; the
      title stays visible
- [ ] No dialog can render taller than the viewport at `lg+`

## Technical spec

- `Sheet`: replace `desktop?: boolean` with
  `variant?: "form" | "document"` defaulting to `"form"`; move the desktop
  panel classes from `sm:` to `lg:`; form uses `lg:max-w-md`, document uses
  `lg:max-w-(--width-doc)`; keep the closed-state
  `lg:translate-y-[calc(100vh_-_2rem)]` clear for the inset dialog and the
  existing explanatory comment, retargeted.
- Callers: `ReviewSheet` and the storefront offering-detail sheet pass
  `variant="document"`; all other callers pass nothing.
- `Modal`: panel `flex max-h-[calc(100vh-2rem)] flex-col`, body
  `mt-4 min-h-0 flex-1 overflow-y-auto`.
- `theme.css`: add `--width-doc: 768px` beside `--width-thread` /
  `--width-panel` / `--width-queue`.
- No API, DB, or token-class change beyond the new variable.

## Tests

- New `frontend/e2e/overlay-standard.spec.ts` at 1280 and 390: a form sheet
  (Edit ABN and tax) is centered and at most 448px wide at desktop and
  bottom-anchored full-width at mobile; the knowledge review is at most 768px
  at desktop; a tall offering-editor modal stays within the viewport.
- Existing role/testid-based specs must pass unchanged: `settings-abn`,
  `settings-voice`, `settings-knowledge`, `business-details-rf2`,
  `knowledge-review`, `knowledge-review-mobile`, `storefront`,
  `rf-7-business-page-shortcuts`, `rf-8-desktop-chat-panel`, `business-hub`,
  `onboarding-go-live`, `onboarding-url`, `rf-9-card-alignment`,
  `mobile-voice-sheet`.
- Unit suites unchanged (sheet tests assert content, not classes).

## Files touched

- `frontend/src/components/ui/Sheet.tsx`
- `frontend/src/components/ui/Modal.tsx`
- `frontend/src/components/knowledge/ReviewSheet.tsx`
- `frontend/src/app/[slug]/Storefront.tsx`
- `frontend/src/styles/theme.css`
- `frontend/e2e/overlay-standard.spec.ts` (new)
- `docs/agencx/design/frontend.md` (4.6 token entry)

## Definition of done

- [ ] Every sheet centers and height-caps at `lg+`; forms and documents get
      their widths; below `lg` unchanged
- [ ] Modal scrolls tall content and never exceeds the viewport
- [ ] The new e2e pins both breakpoints; the sheet-related e2e suite passes
- [ ] `make lint-frontend`, `make typecheck-frontend`, `make test-frontend`
      pass; targeted e2e passes
- [ ] `frontend.md` 4.6 records `--width-doc`

## References

- RF-8 desktop customer chat panel and mobile sheets (archived) - the `lg`
  boundary and the token-shorthand precedent
- RF-6 document-review workspace clarification (archived) - the one existing
  `desktop` caller
- `docs/agencx/design/frontend.md` sections 4.5-4.8
- `frontend/src/lib/useMediaQuery.ts` (`DESKTOP_QUERY`)

## Verification

- `make lint-frontend`, `make typecheck-frontend`, `make test-frontend`: 365
  passed (43 files)
- New `overlay-standard.spec.ts`: 4 passed (form sheet centered at 448px or
  less and content-sized at 1280; bottom-anchored full width at 390; document
  sheet at 768px or less; tall offering Modal capped with a scrolling body)
- Sheet-related regression specs (`settings-abn`, `settings-voice`,
  `settings-knowledge`, `business-details-rf2`, `knowledge-review`,
  `knowledge-review-mobile`, `mobile-voice-sheet`, `storefront`,
  `storefront-mobile`, `rf-7-business-page-shortcuts`,
  `rf-8-desktop-chat-panel`, `business-hub`): 80 passed
