# WREN - Frontend Design System & Surface Specs

> The implementation truth for UI. The pixel standard of `docs/conventions.md` section 6 applies to everything here.
> Design language: **Material 3 tonal clarity** - warm-leaning neutrals, a crimson primary with teal and green functional accents, generous whitespace, Inter throughout.

## 1. The one hard rule: nothing is hardcoded

**No raw color, font, radius, shadow, or duration value ever appears in a component, page, or Tailwind class.** Every visual decision routes through CSS custom properties in exactly one file: `frontend/src/styles/theme.css`. Changing the whole look of Wren means editing only that file (or overriding its variables at runtime for tenant branding).

Three token layers:

```
Layer 1 PRIMITIVES   --primary-20..--primary-95, --neutral-6..--neutral-100...   raw palette, defined once,
                                                                                 referenced ONLY by layer 2
Layer 2 SEMANTIC     --color-bg, --color-text, --color-accent...                 what components are allowed to use
Layer 3 COMPONENT    --button-primary-bg, --chat-bubble-user-bg...               optional; only when a component deviates
```

Rules:

1. Components and pages reference **semantic or component tokens only** - never primitives, never raw values.
2. Hex/rgb/hsl literals are allowed **only** in `theme.css`. A CI check (`frontend/scripts/check-tokens.mjs`, `npm run check:tokens`) fails the build if a color literal appears anywhere else under `src/`. It machine-enforces colors; the rest of rule 1 is enforced in review.
3. Dark mode, tenant branding, and any future theme are **variable overrides**, never component changes.

## 2. Theme file (`frontend/src/styles/theme.css`)

Layer 1 is a Material 3 tonal ramp set: each role (primary crimson, secondary teal, tertiary green, error, neutral) is a ramp of tone steps (higher number = lighter); Layer 2 picks a tone per role and per theme. Dark mode is a systematic derivation (lighter tone of the same ramp), not a parallel palette.

```css
/* LAYER 1: PRIMITIVES (the only place raw values may live) */
:root {
  --primary-20:#67001B;  --primary-30:#870027;  --primary-35:#A1002F;
  --primary-40:#BA0036;  --primary-45:#E21E4A;  --primary-60:#E14A69;
  --primary-70:#F76F86;  --primary-80:#FFB2BC;  --primary-90:#FFD9DC;  --primary-95:#FFECEE;
  --secondary-30:#004F53;  --secondary-40:#00696D;  --secondary-80:#4DD9E2;  --secondary-90:#8EEFF4;
  --tertiary-30:#00522F;  --tertiary-40:#006A45;  --tertiary-45:#008558;
  --tertiary-80:#57DFA2;  --tertiary-90:#C2F2DA;
  --error-30:#93000A;  --error-40:#BA1A1A;  --error-80:#FFB4AB;  --error-90:#FFDAD6;
  --amber-100:#F7EEDC;  --amber-300:#D9B36A;  --amber-500:#B07C24;
  --neutral-100:#FFFFFF;  --neutral-98:#FCF9F8;  --neutral-96:#F6F3F2;  --neutral-94:#F0EDED;
  --neutral-92:#EAE7E7;   --neutral-90:#E5E2E1;  --neutral-10:#1B1C1C;
  --neutral-6:#141313;   --neutral-8:#1B1919;   --neutral-12:#211F20;  --neutral-17:#2B2929;
  --neutral-22:#363334;  --neutral-30:#4A4646;  --neutral-80:#C9C6C5;
  --neutral-variant-30:#5C3F41;  --neutral-variant-50:#906F70;  --neutral-variant-80:#D8C2C3;

  --white:#FFFFFF;
  --scrim:rgb(0 0 0 / 0.4);
  --font-sans: var(--font-inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, ui-sans-serif, sans-serif);
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
}

/* LAYER 2: SEMANTIC (what components use) - LIGHT */
:root {
  --color-bg: var(--neutral-98);
  --color-surface: var(--neutral-100);
  --color-surface-sunken: var(--neutral-96);
  --color-surface-container: var(--neutral-94);
  --color-surface-container-high: var(--neutral-92);
  --color-border: var(--neutral-90);
  --color-border-strong: var(--neutral-variant-50);
  --color-text: var(--neutral-10);
  --color-text-secondary: var(--neutral-variant-30);
  --color-text-tertiary: var(--neutral-variant-50);

  --color-accent: var(--primary-40);
  --color-accent-hover: var(--primary-35);
  --color-accent-active: var(--primary-30);
  --color-accent-subtle: var(--primary-90);
  --color-accent-container: var(--primary-45);
  --color-focus-ring: var(--primary-40);

  --color-success: var(--tertiary-40);  --color-success-subtle: var(--tertiary-90);
  --color-warning: var(--amber-500);    --color-warning-subtle: var(--amber-100);
  --color-danger:  var(--error-40);     --color-danger-subtle:  var(--error-90);
  --color-info:    var(--secondary-40); --color-info-subtle:    var(--secondary-90);

  --radius-sm:8px;  --radius-md:12px;  --radius-lg:16px;  --radius-full:9999px;
  --shadow-1:0 1px 2px rgb(0 0 0 / 0.05);
  --shadow-2:0 2px 8px rgb(0 0 0 / 0.07);
  --shadow-3:0 8px 24px rgb(0 0 0 / 0.10);
  --duration-fast:150ms;  --duration-base:250ms;
  --ease-out: cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

/* LAYER 2 OVERRIDES - DARK. The body below is duplicated verbatim in the
   prefers-color-scheme block so both dark-mode entry paths carry identical tokens. */
:root[data-theme="dark"] {
  --color-bg: var(--neutral-6);
  --color-surface: var(--neutral-12);
  --color-surface-container: var(--neutral-17);
  --color-surface-container-high: var(--neutral-22);
  --color-text: var(--neutral-90);
  --color-accent: var(--primary-80);
  /* ...every other token re-pointed one lighter tone... */
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]):not([data-theme="dark"]) {
    /* the SAME body as the [data-theme="dark"] block, verbatim */
  }
}
```

The two dark blocks must stay literally identical - `src/lib/brand.ts` scopes a tenant's runtime accent override to light mode and relies on both paths carrying the same token body. A header comment in theme.css states this ("edit both or neither"); treat it as load-bearing.

## 3. Tailwind wiring (Tailwind v4)

`frontend/src/app/globals.css` imports `theme.css` and maps semantic tokens into Tailwind utilities via `@theme inline`:

```css
@import "tailwindcss";
@import "../styles/theme.css";

@theme inline {
  --color-bg: var(--color-bg);
  --color-surface: var(--color-surface);
  --color-surface-container: var(--color-surface-container);
  --color-surface-container-high: var(--color-surface-container-high);
  --color-accent: var(--color-accent);
  --color-accent-container: var(--color-accent-container);
  /* ...one line per semantic token... */
  --font-sans: var(--font-sans);
  --radius-md: var(--radius-md);
}
```

The mappings stay **self-referential** (`--color-x: var(--color-x)`) and the `theme.css` import stays **unlayered** - both load-bearing. Components then use `bg-surface`, `text-text-secondary`, `border-border`, `bg-accent-container`, `rounded-md`, etc. Arbitrary values like `bg-[#BA0036]` are what the CI grep forbids.

## 4. Typography, spacing, motion

- **Type scale** (M3-derived, exposed as Tailwind `text-caption` ... `text-display` utilities): 12/16 caption, 13/18 footnote, 14/20 body-sm, **16/24 body (default)**, 18/28 body-lg, 18/26 title-3, 22/28 title-2, 32/40 title-1, 48/56 display. Components reference the semantic `text-*` names, so re-pointing these tokens is the single largest visual lever. Everything uses `--font-sans`; traces/ids/code use `--font-mono` at 13/18.
- **Font loading:** Inter via `next/font/google` in `src/app/layout.tsx` (exposed as `--font-inter`, `display: "swap"`). First build needs network once to cache the font files.
- **Radii:** 8 / 12 / 16 / full.
- **Weight discipline:** regular for prose, medium for labels/buttons, semibold for titles. Weight 700+ is reserved for hero/marketing display only.
- **Spacing:** 4px base grid - allowed steps 4, 8, 12, 16, 24, 32, 48, 64, 96. Card padding 24, page gutters 32 (16 mobile), stack gaps 16.
- **Depth:** flat by default; `--shadow-1` for cards, `--shadow-2` for popovers, `--shadow-3` for modals. Dark mode uses surface steps, not shadows.
- **Motion:** `--duration-fast` hover/press, `--duration-base` enter/exit; `--ease-out` everywhere; honors `prefers-reduced-motion`.

## 5. Per-tenant branding (runtime, data-driven)

`tenant_config.brand` carries at most `{"accent": "#RRGGBB", "display_name": "...", "logo_url": "..."}`.

- The customer surface's server layout injects a scoped override: `<style>:root{--color-accent:{validated};...}</style>`.
- The backend validates `accent` as a hex color at write time; the frontend derives hover/active/subtle steps from it (`src/lib/brand.ts`) and falls back to the default ramp if contrast fails WCAG AA (4.5:1).
- The override applies to the customer surface only; console and platform always keep crimson.
- Logo and display name render in the chat header. That is the entire branding surface - no per-tenant CSS, no per-tenant components.

## 6. Component library (`frontend/src/components/ui/`)

Every component takes only semantic tokens. Each lists its required states.

| Component | Notes | Required states |
|---|---|---|
| `Button` | primary / secondary / ghost / destructive; sm/md | default, hover, active, focus ring, disabled, loading |
| `Input`, `Textarea`, `Select` | label above, help/error below | default, focus, error, disabled |
| `Card` | surface + border + radius-lg + shadow-1 | default, interactive |
| `Table` | sticky header, row hover | loading, empty, error |
| `Badge` | status pill; maps every status vocabulary to a tone (info=open/sent, warning=escalated/claimed/processing/provisioning, success=resolved/closed/active/ready, danger=failed/suspended, neutral=pending/draft/expired) | n/a |
| `Icon` | vendored Material Symbols Outlined SVG, `fill="currentColor"`, `name` -> path registry | n/a |
| `Tabs` | underline style, accent indicator | active, hover, focus |
| `Modal` / `Sheet` | shadow-3, scrim; Sheet for mobile | open/close, focus trap |
| `Toast` | bottom-right, auto-dismiss, functional-token edge | success/error/info |
| `EmptyState` | icon + one-line explanation + primary action | n/a |
| `Skeleton` | shimmer off in reduced-motion | n/a |
| `MetricCard` | bento stat card: big number + label + optional icon/trend/footer | loading, empty, error |
| `Sparkline` | dependency-free inline-SVG polyline, strokes `currentColor` | n/a |
| `FileDropzone` | drag target | idle, drag-over, uploading, done, rejected |
| `ChatBubble` | customer (accent-subtle, right), assistant (surface, left), human_agent (info-subtle), system (centered caption) | static, streaming |
| `StreamingText` | renders SSE tokens, `aria-live="polite"` | streaming, done, interrupted |
| `CitationChip` | inline `[1]` chip; popover shows source + snippet | default, hover |
| `QuoteCard` | renders **pricing-engine output verbatim**; money formatted from integer cents in `src/lib/money.ts` - no arithmetic in components | default, sent |
| `TraceTree` | collapsible run tree (console only), mono font | loading, error, empty |
| `EscalationBanner` | in-chat handoff state | active |

## 7. Surface specs

One Next.js app (App Router). Route groups: `(platform)` -> admin.wren.app, `(tenant-admin)` -> app.wren.app, `(customer)` -> `{slug}.wren.app`, resolved by host middleware. Shared shell: `bg-bg`, max-width content column, `text-text` body.

### 7.1 Surface 3 - Customer chat (`{slug}.wren.app`) - the showpiece

Single screen, centered column (max 720px), tenant logo + name header, message list, composer pinned bottom.

| State | Spec |
|---|---|
| Resolving tenant | full-page skeleton; no flash of default branding (brand injected server-side) |
| Unknown slug | calm 404: "There's no business here." |
| Suspended tenant | "This assistant is currently unavailable." caption, composer hidden |
| Empty conversation | tenant-configured greeting as first assistant bubble; 2-3 starter chips if configured |
| Streaming | StreamingText in assistant bubble; composer disabled with "answering..." hint; stop button |
| Quote in reply | QuoteCard beneath the assistant text |
| Citations | CitationChips on grounded sentences |
| Escalated | EscalationBanner replaces composer; conversation stays readable |
| Error / disconnect | inline retry in the failed bubble, never a blank screen |

### 7.2 Surface 2 - Tenant admin console (`app.wren.app`)

Left sidebar nav: **Onboarding, Knowledge, Conversations, Escalations, Pricing, Dashboards, Settings**. Auth required; tenant scope from membership.

- **Onboarding**: Copilot chat interviews the business and writes config; right-side live summary with a confirm step.
- **Knowledge**: FileDropzone + documents Table (filename, doc_type badge, status badge). Failed rows show error + retry.
- **Conversations**: list -> detail with ChatBubbles + per-message TraceTree drill-down (tool calls, latency, cost). Filter by status.
- **Escalations**: queue Table (reason, conversation, age, status) with claim/resolve actions; resolving posts a `human_agent` reply.
- **Pricing**: pricing_rules Table with inline editor (amount stored as cents) + catalog_items list. Banner: "Changes apply to new quotes only."
- **Dashboards**: bento grid of MetricCards (cost today/month, avg per conversation, conversations, escalation rate) + a 30-day Sparkline card; below it an eval section (per run_type pass/fail with value-vs-threshold chips). Honest empty states - a fresh tenant sees "no eval runs yet", not a blank panel.
- **Settings**: brand editor (accent color + contrast warning, display name, logo URL), escalation threshold slider, tone.

### 7.3 Surface 1 - Platform owner (`admin.wren.app`)

Deliberately minimal, gated by `platform_admins` membership: one Tenants page - Table (name, slug, status, created, conversations, cost) + "Provision tenant" modal + suspend/reactivate actions. Aggregate MetricCards on top.

### 7.4 Marketing surface (apex host `wren.app` / `localhost:3000`)

Public, login-free content served from `app/marketing-surface/` (`proxy.ts` rewrites marketing paths into this segment). Server components use `headers()` + `surfaceUrl()` so links derive from the request host. Shared nav shell. Copy rule: real mechanics only - no invented metrics or testimonials. Four pages: `/product`, `/pricing`, `/demo` (mirrors `docs/DEMO.md`), `/about`.

## 8. Accessibility & quality bar

- WCAG AA contrast on every token pair, plus the runtime brand check (section 5).
- Full keyboard navigation; `:focus-visible` ring on every interactive element; focus traps in modals.
- `aria-live` for streaming and toasts; labeled forms; table semantics.
- Responsive: admin tables collapse gracefully at 768px (horizontal scroll within the card); chat is mobile-first.
- The `docs/conventions.md` section 6 standard applies: if a screen looks off while you're in there - fix it in the shared component/token, not with a local patch.
