# Phase 1 complete - delivered ticket records

Frozen records of every delivered Phase 1 ticket. Nothing here is edited
or maintained; active work lives in `docs/agencx/spec/active/` and the
build dashboard in `docs/agencx/progress.md`. Each file is the ticket as
merged to `development` or `staging`, with its verification narrative.

| File | Tickets | Outcome |
|---|---|---|
| [01-foundation.md](01-foundation.md) | A-1, A-2 | Docs restructure + pointer updates; stood up the canonical set |
| [02-onboarding.md](02-onboarding.md) | O-1, O-2, O-5 through O-12 | Onboarding spine: single-tool turn loop, login-in-chat, interview UI |
| [03-chat-spine.md](03-chat-spine.md) | P-1 through P-5 | Chat spine: provider tiers, failover, agent-ready preload, typing indicator |
| [04-chat-grounding.md](04-chat-grounding.md) | O-3, O-4, C-1 through C-6 | Chat grounding: URL/document ingest, whole-corpus seam, money + escalation guardrails |
| [05-business-page.md](05-business-page.md) | E-1, E-2, E-4 through E-6 | Business page: Home/Chats/Business shell, greeting/brief, business hub |
| [06-polish.md](06-polish.md) | B-1, B-3, D-2, E-3, F-2, G-1 | Polish: copy rename, semantic colour, minimal admin, lean default, import boundary, re-cut evals |
| [07-hygiene.md](07-hygiene.md) | F-1 through F-3 | Hygiene: dead agent code/schema deletion after supervisor topology |
| [09-devex.md](09-devex.md) | K-1 | Developer experience: everything in containers |
| [10-deploy.md](10-deploy.md) | B-4 | Deployment: two containers behind one Vercel origin; live procedure in `docs/agencx/deploy.md` |
| [11-offerings-media.md](11-offerings-media.md) | M-1 through M-6 | Offerings + media: offering identity, Cloudinary media, storefront |
| [12-refinement-r1-r2.md](12-refinement-r1-r2.md) | R-1, R-2 | Completed refinement records; open work in `docs/agencx/spec/active/12-refinement.md` |
| [13-walkthrough.md](13-walkthrough.md) | W-1 through W-9 | Walkthrough fixes + agent contract amendments; current contract summarized in `docs/agencx/design/api-contract.md` |
| [14-schema-drop.md](14-schema-drop.md) | W-10 | Schema drop of `tenant_config.system_prompt`/`.tone`, migration `0029` |
| [15-document-review.md](15-document-review.md) | W-11a, W-11b, W-11c | Document review workspace + privacy disclosure |
| [16-auth-otp-reliability.md](16-auth-otp-reliability.md) | W-12, W-13 | Auth OTP config-drift + resend/cooldown fixes, hosted-verified |
| [17-storefront-redesign.md](17-storefront-redesign.md) | M-7 | Final storefront: no-image-first base, compact catalogs through six offerings, mature browse state from seven, and one header chat entry |
| [19-intent-and-identity.md](19-intent-and-identity.md) | 19 | Intent families and actions on the existing inspection call, escalation-scoped name and email capture, migration `0032` |
| [20-required-services.md](20-required-services.md) | 20 | Required services overview with a rough price, skip-free interview, one knowledge Skip chip, ADR D30 |
| [21-category-management.md](21-category-management.md) | 21 | Category management: controlled category objects, ordered multi-category membership with one primary, migration `0034`, ADR D31 |
| [12-refinement-u1-u4.md](12-refinement-u1-u4.md) | U-1 through U-4 | Shipped UX consistency: nav idiom, button feel, confirm dialog, toasts; walked 2026-10-01 |
| [12-refinement-rf-1-shared-ui.md](12-refinement-rf-1-shared-ui.md) | RF-1 | Shared row grammar, focus visibility and restoration, inner-container scroll restoration, compact chat preview and attention badge |
| [12-refinement-rf-2-business-detail-editing.md](12-refinement-rf-2-business-detail-editing.md) | RF-2 | Post-launch business-detail editing (name, hours, description, contact) with immediate customer-visible consistency |
| [12-refinement-rf-3-offering-search.md](12-refinement-rf-3-offering-search.md) | RF-3 | Offering search on the owner offerings editor and the storefront catalog with one shared predicate; category grouping unchanged |
| [12-refinement-rf-4-pricing-wording.md](12-refinement-rf-4-pricing-wording.md) | RF-4 | Fixed price versus display-only pricing wording: migration `0036`, mutual exclusivity with a 120-char cap, storefront and owner rendering through `money.ts` |
| [12-refinement-rf-5-media-workflows.md](12-refinement-rf-5-media-workflows.md) | RF-5 | One cover/offering-image workflow on a shared media field: explicit remove, local preview while uploading, and failure recovery with no partial state |
| [12-refinement-rf-6-document-review-clarity.md](12-refinement-rf-6-document-review-clarity.md) | RF-6 | Document-review workspace clarity: named draft state, de-duplicated source line, context-specific Discard/Remove labels aligned with the removal dialog, and DOM order matching visual order |
| [12-refinement-rf-7-business-page-shortcuts.md](12-refinement-rf-7-business-page-shortcuts.md) | RF-7 | Browse-first business page with contextual owner shortcuts opening the same RF-2 editors; server-side owner gating, no API or DB change |
| [12-refinement-rf-8-desktop-chat-panel.md](12-refinement-rf-8-desktop-chat-panel.md) | RF-8 | Desktop customer chat panel at `lg+` and full-height mobile sheet, one `CustomerChat` instance preserved across presentations and breakpoints; no API or DB change |
| [12-refinement-rf-9-card-alignment.md](12-refinement-rf-9-card-alignment.md) | RF-9 | Offering, price-summary, and quote cards share one 520px width and `Card` chrome, with a unified header and no API or DB change |
| [12-refinement-rf-10-preferred-name.md](12-refinement-rf-10-preferred-name.md) | RF-10 | Opening-phase preferred-name capture with a persisted two-ask cap (migration `0037`), a name-only `contact` SSE event, and a display-only customer chip with same-tab refresh persistence; ticket 19 handoff capture unchanged |
| [12-refinement-rf-11-ask-for-a-person.md](12-refinement-rf-11-ask-for-a-person.md) | RF-11 | Visible customer chat **Ask for a person** control on a new unauthenticated `POST /api/chat/handoff`, one shared escalation-row writer, deterministic handoff reply with the one contact ask when incomplete, non-terminal and no double handoff; no schema change |
| [12-refinement-rf-12-refresh-restore.md](12-refinement-rf-12-refresh-restore.md) | RF-12 | Same-tab refresh restores the transcript with quote/catalog/price-summary cards from the customer-safe `metadata.response` payload, the unsent composer draft, and the handoff/escalated banner; a formal quote turn captures its card; no schema change |
| [12-refinement-rf-18-owner-read-state.md](12-refinement-rf-18-owner-read-state.md) | RF-18 | Real per-owner read state in the chat queue: migration `0035`, `POST /api/conversations/{id}/read`, unread row emphasis |
| [22-production-hardening.md](22-production-hardening.md) | T-022 to T-033 | Production hardening: abuse control, CI hygiene, Sentry, CSP, conversation delete, retention, operator export, privacy/terms, backups; ADRs D32-D36 |

Evidence:

| File | What it is |
|---|---|
| [evidence/13-walkthrough-round-2.md](evidence/13-walkthrough-round-2.md) | Round-2 observation log feeding W-3 through W-9 |
| [evidence/w-9-reproduction.md](evidence/w-9-reproduction.md) | W-9 E2E reproduction record per conventions section 5 |
