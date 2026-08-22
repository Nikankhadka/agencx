"use client";

import { useEffect, useState } from "react";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { apiFetch } from "@/lib/api";
import { useApiQuery } from "@/lib/useApiQuery";
import { surfaceUrl } from "@/lib/tenant";
import { QrCode } from "./components/QrCode";

/**
 * E-5: the Booking page - the business as a customer finds it, and the link
 * that takes them there. Built from `renderScreen('booking')` in
 * agencx-prototype-v6.html: the name and its one-line description, then "How
 * leads come in" with the shareable link and a copy control.
 *
 * Three parts of the prototype's screen do not ship, each because nothing
 * stands behind it in Stage 1: the cover photo (no image upload, and images are
 * refused by ruling - O-3), the platform buttons (no Google/Facebook/Instagram
 * integrations), and the Services list (quoting is a per-tenant opt-in that is
 * off by default, D-1/D-2). Adding them would be the dead surface the PRD
 * forbids.
 */

interface TenantMe {
  slug: string;
  name: string;
  brand?: Record<string, unknown>;
}

interface OnboardingState {
  draft: Record<string, string>;
}

/**
 * The prototype's subtitle is one line: what the business does, then when it is
 * open. Both come from the O-1 interview, and either may be missing - a
 * business that never answered the hours beat gets the shorter sentence rather
 * than a dangling separator.
 */
function describe(draft: Record<string, string>): string | null {
  const parts = [draft["services"]?.trim(), draft["hours"]?.trim()].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : null;
}

export default function BookingPage() {
  const tenant = useApiQuery<TenantMe>("/api/tenants/me");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    apiFetch<OnboardingState>("/api/onboarding/state")
      .then((state) => setDraft(state.draft ?? {}))
      .catch(() => setDraft({}));
  }, []);

  const slug = tenant.data?.slug;
  // Derived from the current host so the base domain and port carry over -
  // app.localhost:3000 in dev, the real domain in production, never hardcoded.
  // The trailing slash goes: it is the same page either way, and this address
  // is going into a text message or onto a shop window.
  const publicUrl =
    slug && typeof window !== "undefined"
      ? surfaceUrl({ surface: "customer", slug }, window.location.host).replace(/\/$/, "")
      : null;
  // The pill shows the address without its scheme, the way the prototype does;
  // what gets copied is the whole URL, which is what a customer needs.
  const shown = publicUrl?.replace(/^https?:\/\//, "");

  const displayName =
    (tenant.data?.brand?.["display_name"] as string | undefined) ??
    draft["business_name"]?.trim() ??
    tenant.data?.name;
  const subtitle = describe(draft);

  async function copy() {
    if (!publicUrl) return;
    await navigator.clipboard.writeText(publicUrl);
    setCopied(true);
  }

  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden bg-surface">
      <ScreenTopbar title="Booking page" backHref="/business" />
      <div className="min-h-0 flex-1 overflow-y-auto pb-thread-tail lg:mx-auto lg:w-full lg:max-w-thread">
        <div className="px-gutter pt-[18px]">
          <h2 className="mb-1.5 text-display-sm font-bold tracking-[var(--text-display-sm-tracking)] text-text">
            {displayName ?? "Your business"}
          </h2>
          {/* Clamped: the prototype's subtitle is one tight line because Sababa's
              services are, and a real business's list runs to five. Two lines
              is the gist; the full text lives in Settings > Knowledge. */}
          {subtitle ? <p className="line-clamp-2 text-meta text-ink-a40">{subtitle}</p> : null}
        </div>

        <section className="mt-6 border-t border-hairline px-gutter pt-5">
          <h3 className="mb-1.5 text-row-label font-medium text-text">How customers reach you</h3>
          <p className="mb-3.5 text-meta text-ink-a40">
            Share this link and anyone can ask your assistant a question.
          </p>

          {shown ? (
            <div className="flex items-center gap-3 rounded-field border border-hairline bg-surface-sunken px-3.5 py-3">
              <span
                data-testid="booking-link"
                className="min-w-0 flex-1 truncate text-body-sm text-text"
              >
                {shown}
              </span>
              <button
                type="button"
                onClick={copy}
                data-testid="booking-copy"
                className="shrink-0 whitespace-nowrap rounded-chip border-[1.5px] border-accent-a28 px-3.5 py-1.5 text-chip text-accent transition-colors duration-(--duration-fast) active:bg-accent-a07"
              >
                {copied ? "Copied ✓" : "Copy"}
              </button>
            </div>
          ) : (
            <div
              aria-busy="true"
              className="h-12 rounded-field border border-hairline bg-surface-sunken"
            />
          )}

          {publicUrl ? (
            <div className="mt-5 flex flex-col items-center gap-2.5">
              <QrCode value={publicUrl} />
              <p className="text-meta text-ink-a40">Or let them scan this.</p>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
