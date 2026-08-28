"use client";
/* eslint-disable @next/next/no-img-element -- storefront cover is a tenant API response. */

import { useRef, useState } from "react";
import { BrandMark } from "@/components/ui/BrandMark";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import type { StorefrontData } from "@/lib/tenant";
import { CustomerChat } from "./CustomerChat";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function linkLabel(key: string) {
  return key === "website" ? "Website" : key.slice(0, 1).toUpperCase() + key.slice(1);
}

/**
 * The owner's price, rendered. Integer cents in, one string out - this is
 * formatting, not arithmetic: nothing here rounds, marks up, or derives an
 * amount, and an offering with no published price simply shows none.
 */
function priceLabel(cents: number) {
  return `$${(cents / 100).toFixed(2)}`;
}

export function Storefront({
  slug,
  logoUrl,
  greeting,
  starterQuestions,
  storefront,
}: {
  slug: string;
  logoUrl?: string;
  greeting: string | null;
  starterQuestions: string[];
  storefront: StorefrontData;
}) {
  const [chatOpen, setChatOpen] = useState(false);
  // The chat below is mounted for the whole life of this page, so this is
  // filled long before any of the buttons here can be pressed.
  const seedComposer = useRef<((text: string) => void) | null>(null);

  function openChat(message?: string) {
    if (message) seedComposer.current?.(message);
    setChatOpen(true);
  }

  return (
    <main className="mx-auto min-h-dvh w-full max-w-[720px] bg-surface pb-8">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface/95 px-gutter py-3 backdrop-blur">
        <div className="flex min-w-0 items-center gap-2.5">
          <BrandMark logoUrl={logoUrl} name={storefront.name} />
          <span className="truncate text-title-3 font-semibold text-text">{storefront.name}</span>
        </div>
        <button
          type="button"
          onClick={() => openChat()}
          className="flex shrink-0 items-center gap-1.5 rounded-chip bg-accent px-3 py-2 text-chip font-medium text-text-inverse active:opacity-85"
        >
          <Icon name="forum" size={15} />
          Ask a question
        </button>
      </header>

      {storefront.has_cover ? (
        <img
          src={`${API_URL}/api/public/tenant/${encodeURIComponent(slug)}/cover`}
          alt=""
          className="h-56 w-full object-cover sm:h-72"
        />
      ) : null}

      <section className="px-gutter pb-7 pt-8">
        <h1 className="text-display-sm font-bold tracking-[var(--text-display-sm-tracking)] text-text">
          {storefront.name}
        </h1>
        {storefront.tagline ? (
          <p className="mt-3 max-w-prose text-prose text-text-secondary">{storefront.tagline}</p>
        ) : null}
        <button
          type="button"
          onClick={() => openChat(`Hi, I'd like to know more about ${storefront.name}.`)}
          className="mt-5 flex items-center gap-2 rounded-field bg-text px-4 py-3 text-body-sm font-medium text-text-inverse active:opacity-85"
        >
          Talk to {storefront.name}
          <Icon name="arrow_forward" size={16} />
        </button>
      </section>

      {storefront.offerings.length > 0 ? (
        <section className="border-t border-hairline px-gutter py-7">
          <h2 className="text-title-2 font-semibold text-text">What we offer</h2>
          <div className="mt-4 divide-y divide-hairline rounded-card border border-hairline bg-surface">
            {storefront.offerings.map((offering) => (
              <article key={offering.id} className="p-4">
                <div className="flex items-baseline justify-between gap-4">
                  <h3 className="text-card-hl font-medium text-text">{offering.name}</h3>
                  {offering.price_cents !== null ? (
                    <span
                      data-testid="offering-price"
                      className="shrink-0 text-card-hl font-medium text-text tabular-nums"
                    >
                      {priceLabel(offering.price_cents)}
                    </span>
                  ) : null}
                </div>
                {offering.description ? (
                  <p className="mt-1.5 text-body-sm text-text-secondary">{offering.description}</p>
                ) : null}
                <button
                  type="button"
                  onClick={() => openChat(`I'd like to ask about ${offering.name}.`)}
                  className="mt-3 flex items-center gap-1 text-chip font-medium text-accent"
                >
                  Ask about this
                  <Icon name="arrow_forward" size={14} />
                </button>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {storefront.about ? (
        <section className="border-t border-hairline px-gutter py-7">
          <h2 className="text-title-2 font-semibold text-text">About {storefront.name}</h2>
          <p className="mt-3 whitespace-pre-line text-prose text-text-secondary">{storefront.about}</p>
        </section>
      ) : null}

      {Object.keys(storefront.links).length > 0 ? (
        <nav aria-label={`${storefront.name} links`} className="border-t border-hairline px-gutter py-7">
          <h2 className="text-title-2 font-semibold text-text">Find us online</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {Object.entries(storefront.links).map(([key, href]) => (
              <a
                key={key}
                href={href}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 rounded-chip border border-border px-3 py-2 text-chip font-medium text-text hover:bg-surface-container"
              >
                {linkLabel(key)}
                <Icon name="open_in_new" size={13} />
              </a>
            ))}
          </div>
        </nav>
      ) : null}

      <section className="border-t border-hairline px-gutter pt-8 text-center">
        <p className="text-title-3 font-semibold text-text">Have a question?</p>
        <button
          type="button"
          onClick={() => openChat()}
          className="mt-3 inline-flex items-center gap-2 rounded-field bg-accent px-5 py-3 text-body-sm font-medium text-text-inverse active:opacity-85"
        >
          Chat with {storefront.name}
          <Icon name="arrow_forward" size={16} />
        </button>
      </section>

      <Sheet open={chatOpen} onClose={() => setChatOpen(false)} title={`Chat with ${storefront.name}`}>
        <div className="flex h-[calc(85dvh-7rem)] min-h-0 flex-col">
          {/* Deliberately unkeyed: the sheet keeps its children mounted, so a
              customer who closes it and reopens it from another entry point is
              back in the thread they were in, talking to the same conversation
              rather than orphaning it mid-answer. */}
          <CustomerChat
            slug={slug}
            displayName={storefront.name}
            greeting={greeting}
            starterQuestions={starterQuestions}
            composerRef={seedComposer}
          />
        </div>
      </Sheet>
    </main>
  );
}
