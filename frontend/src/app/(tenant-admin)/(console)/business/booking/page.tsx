"use client";

import { useCallback, useEffect, useState } from "react";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { Icon } from "@/components/ui/Icon";
import { apiFetch } from "@/lib/api";
import { CoverPhoto } from "./components/CoverPhoto";
import { PlatformLinks } from "./components/PlatformLinks";
import { StorefrontSectionsEditor } from "./components/StorefrontSectionsEditor";

/**
 * E-5/E-6: the Business page - the business as a customer finds it, and the link
 * that takes them there. Built from `renderScreen('booking')` in
 * agencx-prototype-v6.html: the cover photo, the name and its one-line
 * description, "How leads come in" with the shareable link and the platform
 * tiles, and the Services list.
 *
 * Two parts of the prototype's screen do not ship, by founder decision: the
 * "Get a quote" CTA (quoting is a Stage 2 opt-in and this owner will not use
 * it) and the QR code E-5 added, which was never in the prototype's owner
 * screen and was not being used.
 *
 * The page a customer actually lands on is still the bare chat surface at
 * `(customer)/page.tsx`. Building it out of the storefront prototype is the
 * next ticket; until then the headings here say what this is - a preview of
 * what customers see - and claim nothing that is not true.
 */

interface BookingPage {
  slug: string;
  name: string;
  tagline: string | null;
  links: Record<string, string>;
  has_cover: boolean;
}

export default function BusinessPageScreen() {
  const [page, setPage] = useState<BookingPage | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    apiFetch<BookingPage>("/api/business/page")
      .then(setPage)
      .catch(() => setPage(null));
  }, []);

  useEffect(load, [load]);

  const slug = page?.slug;
  // The tenant's page is a path on this same origin (D22), so the base domain
  // and port carry over for free - localhost:3000 in dev, the real domain in
  // production, never hardcoded. This address goes into a text message or onto
  // a shop window, so it stays as short as the scheme allows.
  const publicUrl =
    slug && typeof window !== "undefined"
      ? `${window.location.origin}/${slug}`
      : null;
  // The pill shows the address without its scheme, the way the prototype does;
  // what gets copied is the whole URL, which is what a customer needs.
  const shown = publicUrl?.replace(/^https?:\/\//, "");

  async function copy() {
    if (!publicUrl) return;
    await navigator.clipboard.writeText(publicUrl);
    setCopied(true);
    // Resets, unlike the prototype's one-way `this.textContent='Copied ✓'` -
    // a control stuck in its confirmed state cannot confirm the next copy.
    window.setTimeout(() => setCopied(false), 2000);
  }

  async function share() {
    if (!publicUrl || !page) return;
    // Web Share where it exists (every phone this is designed for), clipboard
    // everywhere else. No custom sheet: the native one already lists the apps
    // the owner actually has, which a hardcoded four-icon row cannot.
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ title: page.name, url: publicUrl });
        return;
      } catch {
        // Cancelled, or refused by the browser - fall through to copying.
      }
    }
    await copy();
  }

  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden bg-surface">
      <ScreenTopbar title="Business page" backHref="/business" />
      <div className="min-h-0 flex-1 overflow-y-auto pb-thread-tail lg:mx-auto lg:w-full lg:max-w-thread">
        <CoverPhoto hasCover={page?.has_cover ?? false} onChanged={load} />

        <div className="px-gutter pt-[18px]">
          <h2 className="mb-1.5 text-display-sm font-bold tracking-[var(--text-display-sm-tracking)] text-text">
            {page?.name ?? "Your business"}
          </h2>
          {/* Clamped: the prototype's subtitle is one tight line because Sababa's
              services are, and a real business's list runs to five. Two lines
              is the gist; the full text lives in Settings > Knowledge. */}
          {page?.tagline ? (
            <p className="line-clamp-2 text-meta text-ink-a40">
              {page.tagline}
            </p>
          ) : null}
          {publicUrl ? (
            <a
              href={publicUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-flex items-center gap-1.5 rounded-field border border-accent-a28 px-3 py-2 text-chip font-medium text-accent"
            >
              Preview your business page
              <Icon name="open_in_new" size={14} />
            </a>
          ) : null}
        </div>

        {/* `.bk-entry-wrap` - the tinted card holding the link and the tiles. */}
        <section className="mx-gutter mt-3.5 rounded-card bg-accent-a06 p-4">
          <h3 className="mb-1 text-chip font-medium text-accent">
            How customers reach you
          </h3>
          <p className="mb-3.5 text-meta text-ink-a40">
            Share this link and anyone can ask you a question, any time.
          </p>

          {shown ? (
            <div className="mb-3 flex items-center gap-3 rounded-field bg-surface px-3.5 py-2.5">
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
                className="shrink-0 whitespace-nowrap text-chip font-medium text-accent"
              >
                {copied ? "Copied ✓" : "Copy"}
              </button>
            </div>
          ) : (
            <div
              aria-busy="true"
              className="mb-3 h-11 rounded-field bg-surface"
            />
          )}

          <PlatformLinks
            links={page?.links ?? {}}
            onSaved={(links) =>
              setPage((prev) => (prev ? { ...prev, links } : prev))
            }
          />
        </section>

        <StorefrontSectionsEditor />

        {/* `SERVICES` - the owner's own words. Absent when they have saved no
            price list or menu yet; an empty heading over nothing would be the
            dead surface the PRD forbids. */}
        <div className="px-gutter pt-5">
          <button
            type="button"
            onClick={share}
            data-testid="booking-share"
            className="flex w-full items-center justify-center gap-1.5 rounded-field border-[1.5px] border-accent-a28 py-3 text-chip font-medium text-accent active:bg-accent-a07"
          >
            <Icon name="share" size={14} />
            Share
          </button>
        </div>
      </div>
    </main>
  );
}
