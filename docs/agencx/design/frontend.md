# Agencx - Frontend Design System & Surface Specs

The implementation truth for UI. The pixel standard of `docs/conventions.md`
section 6 applies to everything here. Design language: **Material 3 tonal
clarity** - warm-leaning neutrals, a **crimson primary** with teal and green
functional accents, generous whitespace, Plus Jakarta Sans throughout (D17).

The system below is the shipped Wren frontend carried forward; the Agencx
changes are the three-screen manifest (S1/S2/S3), the font swap, the
failover typing indicator (P-5), and the mobile-first app chrome (D18). The
pre-Agencx prototype's teal accent, cleaning copy, and Hivee emblem stay
retired and archived (D17); its mobile-first structure returns as the tenant
app's bottom tab bar (D18).

## 1. The one hard rule: nothing is hardcoded

**No raw color, font, radius, shadow, or duration value ever appears in a
component, page, or Tailwind class.** Every visual decision routes through CSS
custom properties in exactly one file: `frontend/src/styles/theme.css`.
Changing the whole look means editing only that file (or overriding its
variables at runtime for tenant branding).

Three token layers:

```
Layer 1 PRIMITIVES   --primary-20..--primary-95, --neutral-6..--neutral-100...   raw palette, defined once,
                                                                                  referenced ONLY by layer 2
Layer 2 SEMANTIC     --color-bg, --color-text, --color-accent...                 what components are allowed to use
Layer 3 COMPONENT    --button-primary-bg, --chat-bubble-user-bg...               optional; only when a component deviates
```

Rules:

1. Components and pages reference **semantic or component tokens only** - never
   primitives, never raw values.
2. Hex/rgb/hsl literals are allowed **only** in `theme.css`. A CI check
   (`frontend/scripts/check-tokens.mjs`, `npm run check:tokens`) fails the build
   if a color literal appears anywhere else under `src/`. It machine-enforces
   colors; the rest of rule 1 is enforced in review.
3. Dark mode, tenant branding, and any future theme are **variable overrides**,
   never component changes.

## 2. Theme file (`frontend/src/styles/theme.css`)

Layer 1 is a Material 3 tonal ramp set: each role (primary crimson, secondary
teal, tertiary green, error, neutral) is a ramp of tone steps (higher number =
lighter); Layer 2 picks a tone per role and per theme. Dark mode is a
systematic derivation (lighter tone of the same ramp), not a parallel palette.

The crimson primary ramp is shipped and unchanged from the Wren rebrand
(`--primary-40:#BA0036` accent, `--primary-90/95` subtle fills). The one Agencx
token change is the font:

```
--font-sans: var(--font-plus-jakarta, ...sans-serif);
```

wired via `next/font/google` Plus Jakarta Sans in `layout.tsx` (replacing Inter;
`display: "swap"`). Component code is untouched - the swap is a re-point, the
same load-bearing pattern the Wren rebrand proved.

**Colour convention (semantic status colours).** Crimson is the **brand** primary
and is reserved for brand accents only: primary buttons, active tab/nav, links,
focus rings, the monogram, and progress fill on brand surfaces. It is never used
for a *status* meaning. Status is expressed with the standard semantic ramp,
routed through the semantic tokens (Layer 2) and the `Badge` `STATUS_TONE` map:

- **Green** (`--color-success`): approved, success, complete, paid, ready,
  resolved, active, delivered, confirmed.
- **Red** (`--color-danger`): cancelled, declined, failed, suspended, rejected,
  refunded, error.
- **Amber** (`--color-warning`): pending, warning, overdue, in-progress,
  provisioning, processing, claimed, escalated, outstanding.
- **Neutral / info** (grey, or `--color-info` where a distinct info colour is
  wanted): open, sent, draft, neutral - any status without a clear
  good/bad/pending charge.

When a screen needs a status the component maps the status string to a tone via
`toneForStatus` (Badge.tsx) - never a hardcoded hex. Unknown/tenant-defined
statuses fall back to neutral. (This convention lands in shipped code via ticket
B-3; the reference prototypes already reflect it.)

**Lighter primary - SHIPPED (O-5, was B-3 US-1).** The brand accent is
`#C1123F` (a touch lighter than the original `#BA0036`, still crimson, white-text
AA on primary), with the derived ramp hover `#A80033`, active `#8F0029`,
accent-container `#E8385E`; subtle `#FFD9DC`/`#FFECEE` unchanged. Landed with
O-5 rather than B-3, because the onboarding thread is ported from a prototype
carrying that exact ramp. `--neutral-10` also moved to the prototype's warmer
ink `#1A1A18`.

**The alpha ladder (O-5).** The prototype expresses every soft surface as one
hue at an alpha step, so `theme.css` carries two channel triples -
`--primary-40-rgb` and `--neutral-10-rgb` - and derives a ladder from them:
`--color-accent-a07/09/12/16/28/45/50` and
`--color-ink-a05/07/12/35/40`. These are named by alpha step rather than by role
because the prototype reuses each step in several places; a numeric name stays
honest where an invented role vocabulary would not. Only steps a shipped screen
uses are defined - add one when a screen needs it, never speculatively. Note
that `--color-ink-a40` (the prototype's `--c-muted`) is what thread surfaces use
for muted text, NOT the mauve `--color-text-tertiary`.

**Thread tokens (O-5).** The onboarding thread's type (`--text-lede`,
`--text-lede-q`, `--text-bubble`), geometry (`--radius-bubble-lg`,
`--space-thread-*`, `--size-send*`, `--size-code-cell-*`, `--width-thread`) and
motion (`--duration-rise-fast`, `--duration-veil`) are all prototype values. Some
gaps are deliberately off the 4px grid (14px, 18px) - where the prototype and
the grid guidance in section 4 disagree, the prototype wins.

**Tailwind v4 has no `--duration` namespace.** `duration-fast` is not a real
utility and silently does nothing; the form that reads a token is
`duration-(--duration-fast)`. `--animate-*` IS a namespace, so named animations
(`animate-rise`, `animate-beat-in`) are declared in `globals.css` and used
directly.

**Dark mode:** the two dark blocks (`:root[data-theme="dark"]` and the
`prefers-color-scheme` media block) must stay literally identical - a header
comment states this ("edit both or neither"); treat it as load-bearing.

## 3. Tailwind wiring (Tailwind v4)

`frontend/src/app/globals.css` imports `theme.css` and maps semantic tokens into
Tailwind utilities via `@theme inline` - self-referential mappings
(`--color-x: var(--color-x)`), the `theme.css` import stays **unlayered**. Both
are load-bearing. Components use `bg-surface`, `text-text-secondary`,
`border-border`, `bg-accent-container`, `rounded-md`, etc. Arbitrary values like
`bg-[#BA0036]` are what the CI grep forbids.

## 4. Typography, spacing, motion

- **Type scale** (M3-derived, exposed as `text-caption` ... `text-display`
  utilities): 12/16 caption, 13/18 footnote, 14/20 body-sm, **16/24 body
  (default)**, 18/28 body-lg, 18/26 title-3, 22/28 title-2, 32/40 title-1,
  48/56 display. Components reference the semantic `text-*` names; re-pointing
  these tokens is the single largest visual lever. Everything uses
  `--font-sans`; traces/ids/code use `--font-mono` at 13/18.
- **Radii:** 8 / 12 / 16 / full.
- **Weight discipline:** regular for prose, medium for labels/buttons, semibold
  for titles. Weight 700+ is reserved for hero/marketing display only.
- **Spacing:** 4px base grid - allowed steps 4, 8, 12, 16, 24, 32, 48, 64, 96.
  Card padding 24, page gutters 32 (16 mobile), stack gaps 16.
- **Depth:** flat by default; `--shadow-1` for cards, `--shadow-2` for
  popovers, `--shadow-3` for modals. Dark mode uses surface steps, not shadows.
- **Motion:** `--duration-fast` hover/press, `--duration-base` enter/exit;
  `--ease-out` everywhere; honors `prefers-reduced-motion`.

## 5. Per-tenant branding (runtime, data-driven)

`tenant_config.brand` carries at most `{"accent": "#RRGGBB", "display_name":
"...", "logo_url": "..."}`.

- The customer surface's server layout injects a scoped override:
  `<style>:root{--color-accent:{validated};...}</style>`.
- The backend validates `accent` as a hex color at write time; the frontend
  derives hover/active/subtle steps from it (`src/lib/brand.ts`) and falls back
  to the default ramp if contrast fails WCAG AA (4.5:1).
- The override applies to the customer surface only; console and platform always
  keep crimson.
- Logo and display name render in the chat header. That is the entire branding
  surface - no per-tenant CSS, no per-tenant components.

## 6. Component library (`frontend/src/components/ui/`)

Every component takes only semantic tokens. Each lists its required states.

| Component | Notes | Required states |
|---|---|---|
| `Button` | primary / secondary / ghost / destructive; sm/md | default, hover, active, focus ring, disabled, loading |
| `Input`, `Textarea`, `Select` | label above, help/error below; the inactive send state is the only validation signal - no red error text | default, focus, error, disabled |
| `CommandPill` | `command` (send circle appears with text) and `field` (circle always present, dimmed until valid) variants; the pill carries the focus ring, never a rectangle inside it; `.pill-plus` opens the file picker where attaching is offered (O-3) | empty, typing, armed, busy/stop, disabled, attach |
| `Card` | surface + border + radius-lg + shadow-1 | default, interactive |
| `Table` | sticky header, row hover | loading, empty, error |
| `Badge` | status pill; maps every status vocabulary to a tone (info=open/sent, warning=escalated/claimed/processing/provisioning, success=resolved/closed/active/ready, danger=failed/suspended, neutral=pending/draft/expired) | n/a |
| `Icon` | vendored Material Symbols Outlined SVG, `fill="currentColor"`, `name` -> path registry | n/a |
| `Tabs` | underline style, accent indicator | active, hover, focus |
| `Modal` / `Sheet` | shadow-3, scrim; Sheet for mobile | open/close, focus trap |
| `Toast` | bottom-right, auto-dismiss, functional-token edge; text only, no celebration | success/error/info |
| `EmptyState` | icon + one-line explanation + primary action; never bare "no data" | n/a |
| `Skeleton` | shimmer off in reduced-motion | n/a |
| `MetricCard` | bento stat card: big number + label + optional icon/trend/footer | loading, empty, error |
| `Sparkline` | dependency-free inline-SVG polyline, strokes `currentColor` | n/a |
| `ScreenTopbar` (O-3) | `.dst-topbar`: 58px, back control, title, optional trailing action, hairline rule | default |
| `RowLink` (O-3) | `.bh-row`: icon, label, chevron, hairline - a hub screen's list of destinations | default, pressed |
| `FileDropzone` | drag target; accepted PDF, DOCX, MD/TXT/CSV/JSON. **Images are refused** - nothing in the stack reads one (no OCR, no vision call), founder ruling 2026-08-22; a vision call on the provider seam is the upgrade path | idle, drag-over, uploading, done, rejected |
| `ChatBubble` | the OPERATOR thread idiom: customer (accent-subtle, right), assistant (surface, left), human_agent (info-subtle), system (centered caption); 18px radius, tip at the top | static, streaming |
| `Thread` (O-5) | the ONBOARDING thread idiom, a separate design: `Thread`, `LedeMessage`, `AgentLine` (bare prose), `OwnerBubble` (20px, tip bottom-right), `TypingLine`, `ThreadPill`, `ThreadVeil`. Never merge with `ChatBubble` | static, streaming, pending |
| `StreamingText` | renders SSE tokens, `aria-live="polite"` | streaming, done, interrupted |
| `TypingIndicator` | **NEW (P-5):** three pulsing dots (600-800ms) shown while a turn is in flight, sustained through the failover window - never a spinner, never a blank | active |
| `CitationChip` | inline `[1]` chip; popover shows source + snippet | default, hover |
| `QuoteCard` | renders **pricing-engine output verbatim**; money formatted from integer cents in `src/lib/money.ts` - no arithmetic in components | default, sent |
| `TraceTree` | collapsible run tree (console only), mono font | loading, error, empty |
| `EscalationBanner` | in-chat handoff state | active |

## 7. Surface specs

One Next.js app (App Router). Route groups: `(platform)` -> admin host,
`(tenant-admin)` -> app host, `(customer)` -> `{slug}` host, resolved by host
middleware (`proxy.ts`). Shared shell: `bg-bg`, max-width content column,
`text-text` body.

### S1 - Chat (tenant app tab 1) - login-in-chat, interview, everyday chat

The product opens into a conversation, not a home screen. The first
conversation IS the product.

- **Login-in-chat (NEW, O-2):** the owner types an email in the command pill;
  send activates on valid email format (no error text). A 6-digit code is sent
  to that address; six digit cells replace the input footprint (auto-focus
  first cell, numeric keyboard on mobile), auto-submit on six valid digits. One
  line echoes the destination with a "Wrong email?" affordance; resend is
  inactive for 30 seconds with no visible countdown; wrong-code/expired/
  max-attempts each get one calm line. Duplicate email sends the code regardless
  (no account-existence leak); success silently continues. No toast, no
  celebration.
- **Interview:** the same conversation continues as the onboarding interview
  (name, business name, business type, headcount, hours, what they sell).
  Business type drives questions from config, never code (I8).
- **Everyday chat:** after go-live, the Chat tab holds the Copilot
  conversation.

The thread is the progress indicator: no progress bars, no "% complete"
anywhere. After go-live the app has exactly two tabs: Chat and Business.

**Shipped shape (O-5).** Both halves of this conversation - `/login`
(login-in-chat) and `/onboarding` (the interview) - render on the shared
primitives in `frontend/src/components/ui/Thread.tsx`, ported from the
prototype's ONBOARDING screen. The thread IS the screen: `/onboarding` renders
chrome-free (no sidebar, no hamburger header), there is no title, and there is no
progress surface of any kind. Assistant turns are bare prose; only the owner's
turns get a bubble. A crimson veil (`#s1-grad`) sits over the bottom 56% and
fades for good once the owner has answered once.

`Thread.tsx` is deliberately NOT `ChatBubble`: the operator thread's two-bubble
idiom (18px radius, tip at the top) and the onboarding thread's idiom (bare prose
plus a 20px owner bubble tipped bottom-right) are different designs in the
prototype. Do not unify them.

**Email in a chat composer (O-5).** The client gate on the login pill is
*liveness only* - it arms the send circle when the text contains something
address-shaped, so "it's sam@shop.com" is sendable. The authority is
`backend/app/services/email_address.py`, which extracts an address from prose,
normalizes it, and validates syntax; a bad address comes back as a 400 with one
calm conversational line the thread renders verbatim, and the typed text stays
put so it can be corrected. Deliverability is not checked - the code itself is
that test, and "Wrong email?" is already on screen.

| State | Spec |
|---|---|
| Resolving tenant | full-page skeleton; no flash of default branding (brand injected server-side) |
| Login / no valid session | chat surface present with the agent's first message already rendered - no welcome screen |
| Opening message | held behind the typing indicator for 820ms, then revealed as the lede - static messages are paced like streamed ones (section 9). Never re-paced for restored history |
| Bad email typed | one calm line under the composer from the server; typed text kept |
| Streaming | StreamingText in assistant bubble; TypingIndicator up while the turn is in flight (through the failover window, P-5); composer disabled with "answering..." hint; stop button |
| Escalated | EscalationBanner replaces composer; conversation stays readable |
| Error / disconnect | inline retry in the failed bubble, never a blank screen |
| Drop-off / return | full history renders from server (last 20 turns), scrolled to the most recent message; input state matches the in-progress beat |

### S2 - Business (tenant app tab 2) - show-back of profile + knowledge

The Business tab displays the profile and knowledge the owner gave the agent -
what the assistant believes about the business, and the uploaded material it
answers from - so the owner can trust and correct it. Editable through the
Copilot ("change my rate to $160"), never through settings forms. No
configuration that exists only as a toggle.

The thin, product-required exceptions: a "live / not live" indicator, the share
link + QR, and the **enabled-tools toggle (D-3)** - the per-tenant on/off for
recommendations / quoting / order lookup that implements tool gating (PRD
section 8). These are scope, not settings-tree creep (decision 7).

The knowledge half now lives at **Settings > Knowledge** (`/settings/knowledge`,
O-3 / D19) and is not a document table: a source is processed into fixed readable
sections the owner corrects, held as a draft until they save it. E-1 re-homes
this screen inside the two-tab shell.

| State | Spec |
|---|---|
| Empty | One line plus the two ways in (paste a link, add a document); no table, no type picker |
| Reading | The `.proc-txt` line naming the work ("Reading your site...") while a source is fetched and processed |
| Review (draft) | Bottom sheet: the sections as editable text, Save / Discard. Nothing answers a customer until Save |
| Active | Each source shown as its sections, with its own status line; edit reopens the sheet |
| Failed | The reason in place, plus retry (re-runs the ingest over the stored text) |
| Tool toggles | Enabled-tools section (D-3); toggling updates `tenant_config.enabled_tools` |

### S3 - Public page (anonymous, per-tenant slug)

Single screen, centered column (max ~720px), tenant logo + display name header,
message list, composer pinned bottom. No auth. Share link + QR for distribution.

| State | Spec |
|---|---|
| Resolving tenant | Full-page centered skeleton; no flash of default branding |
| Unknown slug | Calm 404: "There's no business here." |
| Suspended tenant | "This assistant is currently unavailable." caption, composer hidden |
| Empty conversation | Tenant-configured greeting as the first assistant bubble; starter chips if configured |
| Streaming | StreamingText in assistant bubble; TypingIndicator through the failover window (P-5); composer disabled with "answering..." hint; stop button |
| Citations | CitationChips on grounded sentences |
| Escalated | EscalationBanner replaces composer-state messaging; conversation stays readable |
| Error / disconnect | Inline retry in the failed bubble, never a blank screen |

### Tenant console shell (nav re-cut, E-1/E-2)

Left sidebar nav re-cut to **Chat** and **Business** (E-1). The advanced Wren
screens (Conversations with traces, Dashboards, Escalations, Pricing) are
removed from the tenant nav but their routes and code remain (E-2), reachable by
the platform owner until Stage 2 re-lands them. Platform admin stays minimal
(E-3): one Tenants page (list, provision, suspend/reactivate) plus aggregate
metrics.

### Mobile-first app chrome (tenant app, D18)

The tenant app is mobile-first: below `lg` the two-tab manifest renders as an
app-style surface with a persistent **bottom tab bar** - Chat and Business as
bottom tabs; at `lg+` the left sidebar stays (E-1). One codebase, responsive; no
native app, no PWA shell in Stage 1.

- Tab bar: icon + label per tab, minimum 44px touch target, ~64px height plus
  `env(safe-area-inset-bottom)` padding for home-indicator devices
- Active tab: accent-container pill with the filled Material Symbol; inactive:
  quiet text with the outlined glyph - the same idiom as the sidebar items
- The hamburger Drawer is no longer the tenant app's mobile nav; it stays
  available to the platform surface (E-3)
- Brand header stays compact on mobile; sign-out is reachable, never hidden
- Structural reference: the reworked prototype
  (`docs/agencx/design/prototypes/agencx-prototype-v6.html`) is trusted for
  screen inventory, states, interaction vocabulary, and the bottom tab bar
  pattern, now carrying the shipped crimson identity, the monogram mark, and
  the Sababa reference tenant (D17, D18). The companion storefront surface
  (`agencx-storefront-customer-v3.html`) is a retired pre-D18 surface kept for
  storefront interaction vocabulary only

## 8. SSE event contract

| Event | When emitted | Subscribed surfaces update |
|---|---|---|
| `onboarding_beat_completed` | A capture beat promotes to confirmed | Business tab (show-back surface) |
| `escalation_triggered` | Agent escalates to tenant | Chat thread, EscalationBanner |
| `turn_started` | A customer turn begins (send) | TypingIndicator enters active (P-5) |
| `failover_engaged` | Primary timed out, fallback raced (never customer-visible text) | Tracing/cost attributes only; the TypingIndicator keeps animating |

## 9. Interaction rules (load-bearing)

- **No welcome screen, no progress bars, no celebration.** The thread is the
  progress indicator.
- **Typing indicator before static messages** - conversational pacing must feel
  consistent from the first beat; the indicator must never stop mid-turn to
  reveal a provider switch (P-5).
- **Confirmation-card pattern** for every action that touches money or
  customer-facing records (Stage 2; Stage 1 has no autonomous writes).
- **No undo bar** - the confirmation card covers the same ground.
- **No raw structured data in user-facing output** - JSON, XML, markdown tables,
  or code blocks never render in chat. Parse and present through UI components,
  or show an honest fallback message.
- **Natural-language summaries only** - lists use conversational framing ("Here's
  what I know:"), never bullet points or markdown.
- **No impersonation** - every agent identifies as an assistant acting on behalf
  of Agencx, never as the business owner or as human.

## 10. Accessibility & quality bar

- WCAG AA contrast on every token pair, plus the runtime brand check (section 5)
- Full keyboard navigation; `:focus-visible` ring on every interactive element;
  focus traps in modals
- `aria-live` for streaming and toasts; labeled forms; table semantics
- Responsive: admin tables collapse gracefully at 768px (horizontal scroll
  within the card); the tenant app is mobile-first (bottom tab bar below `lg`,
  D18); chat is mobile-first; minimum touch target 44px
- Tab bar: `aria-current` on the active tab, visible labels on every tab,
  keyboard navigation, safe-area padding honored
- The `docs/conventions.md` section 6 standard applies: if a screen looks off
  while you're in there - fix it in the shared component/token, not with a local
  patch