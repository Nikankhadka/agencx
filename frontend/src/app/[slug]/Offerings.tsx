"use client";
/* eslint-disable @next/next/no-img-element -- offering media is a tenant API response. */

import { useEffect, useMemo, useRef, useState } from "react";
import { navTone } from "@/components/ui/TabBar";
import type { StorefrontOffering } from "@/lib/tenant";

interface Section {
  id: string;
  label: string;
  offerings: StorefrontOffering[];
}

const COMPACT_CATALOG_MAX_ITEMS = 6;

function sectionsOf(offerings: StorefrontOffering[]): Section[] {
  const categories = Array.from(
    new Set(offerings.map((item) => item.category).filter(Boolean)),
  ) as string[];
  const hasUncategorized = offerings.some((item) => !item.category);
  const grouped =
    categories.length > 1 ? [...categories, ...(hasUncategorized ? ["More"] : [])] : ["More"];
  return grouped.map((category, index) => ({
    id: `offer-category-${index + 1}`,
    label: categories.length <= 1 ? "What we offer" : category,
    offerings: offerings.filter(
      (item) => categories.length <= 1 || (item.category || "More") === category,
    ),
  }));
}

/**
 * The owner's price, rendered. Integer cents in, one string out - this is
 * formatting, not arithmetic: nothing here rounds, marks up, or derives an
 * amount, and an offering with no published price simply shows none.
 */
export function priceLabel(cents: number) {
  return `$${(cents / 100).toFixed(2)}`;
}

function RowMedia({ offering }: { offering: StorefrontOffering }) {
  const [failed, setFailed] = useState(false);
  const media = offering.media;
  if (media?.type === "video") {
    if (media.poster_url && !failed) {
      return (
        <span className="relative h-24 w-24 shrink-0">
          <img
            src={media.poster_url}
            alt=""
            loading="lazy"
            onError={() => setFailed(true)}
            className="size-full rounded-field object-cover"
          />
          <span className="absolute bottom-1.5 left-1.5 rounded-chip bg-scrim px-2 py-1 text-meta text-text-inverse">
            Video
          </span>
        </span>
      );
    }
    return (
      <span className="grid h-24 w-24 shrink-0 place-items-center rounded-field bg-surface-container text-meta text-text-secondary">
        Video
      </span>
    );
  }
  if (media?.type === "image" && media.url) {
    if (failed) {
      // A deleted asset falls back to a letter tile, never a broken-image icon.
      const initial = offering.name.trim().charAt(0).toUpperCase() || "?";
      return (
        <span
          aria-hidden
          className="grid h-24 w-24 shrink-0 place-items-center rounded-field bg-surface-container text-title-2 font-semibold text-text-tertiary"
        >
          {initial}
        </span>
      );
    }
    return (
      <img
        src={media.url}
        alt=""
        loading="lazy"
        onError={() => setFailed(true)}
        className="h-24 w-24 shrink-0 rounded-field object-cover"
      />
    );
  }
  return null;
}

function OfferingRow({
  offering,
  onSelect,
}: {
  offering: StorefrontOffering;
  onSelect: (offering: StorefrontOffering) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(offering)}
      className="flex w-full items-start justify-between gap-4 border-b border-hairline py-4 text-left transition-colors duration-(--duration-fast) last:border-b-0 hover:bg-surface-container active:bg-surface-container-high sm:px-3"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-card-hl font-semibold text-text">{offering.name}</span>
        {offering.price_cents !== null ? (
          <span
            data-testid="offering-price"
            className="mt-1 block text-body-sm font-medium text-text tabular-nums"
          >
            {priceLabel(offering.price_cents)}
          </span>
        ) : null}
        {offering.description ? (
          <span className="mt-2 line-clamp-3 text-body-sm text-text-secondary">
            {offering.description}
          </span>
        ) : null}
      </span>
      <RowMedia offering={offering} />
    </button>
  );
}

/**
 * M-7 offering list (v5 sparse amendment): small catalogs stay in one compact
 * region without browse chrome, while mature catalogs retain category nav and
 * scrollspy. Rows reserve no media space in either mode - thumbnails render
 * only where media exists.
 */
export function Offerings({
  offerings,
  onSelect,
}: {
  offerings: StorefrontOffering[];
  onSelect: (offering: StorefrontOffering) => void;
}) {
  const sections = useMemo(() => sectionsOf(offerings), [offerings]);
  const isCompact = offerings.length <= COMPACT_CATALOG_MAX_ITEMS;
  const [activeId, setActiveId] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || isCompact || sections.length < 2) return;
    const targets = sections
      .map((section) => root.querySelector(`#${CSS.escape(section.id)}`))
      .filter((el): el is Element => el !== null);
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActiveId(entry.target.id);
        }
      },
      { rootMargin: "-30% 0px -60% 0px" },
    );
    targets.forEach((target) => observer.observe(target));
    return () => observer.disconnect();
  }, [isCompact, sections]);

  const active = activeId ?? sections[0]?.id;

  if (isCompact) {
    const singleGroup = sections.length === 1;
    return (
      <div
        ref={rootRef}
        data-testid="compact-offerings"
        className="w-full border-t border-hairline"
      >
        <section className="mx-auto max-w-5xl px-gutter py-6">
          <h2 className="text-title-2 font-semibold text-text">What we offer</h2>
          {singleGroup ? (
            <div className="mt-3 grid min-w-0 sm:grid-cols-2 sm:gap-x-8">
              {sections[0]?.offerings.map((offering) => (
                <OfferingRow key={offering.id} offering={offering} onSelect={onSelect} />
              ))}
            </div>
          ) : (
            <div className="mt-6 grid min-w-0 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {sections.map((section) => (
                <section key={section.id} className="min-w-0">
                  <h3 className="text-footnote font-semibold text-text-secondary">
                    {section.label}
                  </h3>
                  <div className="mt-1">
                    {section.offerings.map((offering) => (
                      <OfferingRow key={offering.id} offering={offering} onSelect={onSelect} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </section>
      </div>
    );
  }

  return (
    <div ref={rootRef} data-testid="browse-offerings" className="w-full border-t border-hairline">
      {sections.length > 1 ? (
        <nav
          aria-label="Offer categories"
          className="sticky top-16 z-10 flex gap-2 overflow-x-auto border-b border-hairline bg-surface/95 px-gutter py-3 backdrop-blur lg:hidden"
        >
          {sections.map((section) => {
            const isActive = section.id === active;
            return (
              <a
                key={section.id}
                href={`#${section.id}`}
                aria-current={isActive ? "true" : undefined}
                className={`min-h-11 shrink-0 whitespace-nowrap rounded-chip px-4 py-3 text-chip font-medium transition-colors duration-(--duration-fast) ${
                  isActive
                    ? navTone(true, "")
                    : `bg-surface-container ${navTone(false, "text-text-secondary")}`
                }`}
              >
                {section.label}
              </a>
            );
          })}
        </nav>
      ) : null}

      <div className="mx-auto max-w-5xl lg:grid lg:grid-cols-4 lg:gap-8 lg:px-gutter">
        {sections.length > 1 ? (
          <aside className="hidden lg:col-span-1 lg:block">
            <nav aria-label="Offer categories" className="sticky top-24 py-8">
              <p className="mb-3 text-title-3 font-semibold text-text">Browse</p>
              <ul className="space-y-1">
                {sections.map((section) => {
                  const isActive = section.id === active;
                  return (
                    <li key={section.id}>
                      <a
                        href={`#${section.id}`}
                        aria-current={isActive ? "true" : undefined}
                        className={`block min-h-11 rounded-field px-3 py-3 text-body-sm transition-colors duration-(--duration-fast) ${navTone(isActive, "text-text-secondary")}`}
                      >
                        {section.label}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </nav>
          </aside>
        ) : null}

        <div className={sections.length > 1 ? "lg:col-span-3" : "lg:col-span-4"}>
          {sections.map((section) => (
            <section
              key={section.id}
              id={section.id}
              className="scroll-mt-32 border-b border-hairline px-gutter py-8 last:border-b-0 lg:px-0"
            >
              <h2 className="text-title-2 font-semibold text-text">{section.label}</h2>
              <div className="mt-3 grid min-w-0 sm:grid-cols-2 sm:gap-x-8">
                {section.offerings.map((offering) => (
                  <OfferingRow
                    key={offering.id}
                    offering={offering}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
