"use client";
/* eslint-disable @next/next/no-img-element -- offering media is a tenant API response. */

import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { navTone } from "@/components/ui/TabBar";
import { formatCents } from "@/lib/money";
import { filterOfferings } from "@/lib/offering-search";
import type { StorefrontOffering } from "@/lib/tenant";

interface Section {
  id: string;
  label: string;
  offerings: StorefrontOffering[];
}

const COMPACT_CATALOG_MAX_ITEMS = 6;

function sectionsOf(offerings: StorefrontOffering[]): Section[] {
  const names: string[] = [];
  for (const offering of offerings) {
    const memberships = offering.categories?.length
      ? offering.categories
      : offering.category
        ? [{ name: offering.category }]
        : [];
    for (const category of memberships) {
      if (!names.includes(category.name)) names.push(category.name);
    }
  }
  const uncategorized = offerings.filter(
    (offering) => !(offering.categories?.length || offering.category),
  );
  if (names.length <= 1 && !uncategorized.length) {
    return [{ id: "offer-category-1", label: "What we offer", offerings }];
  }
  const sections = names.map((name, index) => ({
    id: `offer-category-${index + 1}`,
    label: name,
    offerings: offerings.filter((offering) =>
      (offering.categories?.length
        ? offering.categories.some((category) => category.name === name)
        : offering.category === name),
    ),
  }));
  if (uncategorized.length) {
    sections.push({
      id: `offer-category-${sections.length + 1}`,
      label: names.length ? "More" : "What we offer",
      offerings: uncategorized,
    });
  }
  return sections;
}

/**
 * RF-4: the owner's pricing, rendered. A fixed price goes through `money.ts`
 * (integer cents in, one string out - no arithmetic here); pricing wording is
 * display text, shown verbatim and never treated as an amount. An offering with
 * neither simply shows none.
 */
export function priceLabel(cents: number) {
  return formatCents(cents);
}

/** The offering's price line: formatted cents, else verbatim wording, else null. */
function priceLine(offering: StorefrontOffering): string | null {
  if (offering.price_cents !== null) return priceLabel(offering.price_cents);
  return offering.pricing_wording?.trim() || null;
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
        {priceLine(offering) ? (
          <span
            data-testid="offering-price"
            className="mt-1 block text-body-sm font-medium text-text tabular-nums"
          >
            {priceLine(offering)}
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
 * RF-3: the catalog is loaded whole on the server and handed down as props, so
 * the search filters it in memory rather than round-tripping per keystroke.
 */
function SearchInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="command-pill flex items-center gap-2 rounded-field border border-border bg-surface px-4">
      <span className="shrink-0 text-text-tertiary">
        <Icon name="search" size={18} />
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Search offerings…"
        aria-label="Search offerings"
        data-testid="storefront-search"
        className="min-w-0 flex-1 bg-transparent py-3 text-body-sm text-text outline-none placeholder:text-text-tertiary"
      />
    </div>
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
  const [search, setSearch] = useState("");
  // The compact/browse split is the catalog's own size, not the filtered one,
  // so searching never changes the layout mode.
  const visible = useMemo(() => filterOfferings(offerings, search), [offerings, search]);
  const sections = useMemo(() => sectionsOf(visible), [visible]);
  const isCompact = offerings.length <= COMPACT_CATALOG_MAX_ITEMS;
  const searchUi = <SearchInput value={search} onChange={setSearch} />;
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
          <div className="mt-3">{searchUi}</div>
          {visible.length === 0 ? (
            <p
              data-testid="storefront-no-matches"
              className="mt-3 text-prose text-text-secondary"
            >
              No offerings match your search.
            </p>
          ) : singleGroup ? (
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
      <div className="mx-auto max-w-5xl px-gutter pt-6">{searchUi}</div>
      {visible.length === 0 ? (
        <p
          data-testid="storefront-no-matches"
          className="mx-auto max-w-5xl px-gutter py-8 text-prose text-text-secondary"
        >
          No offerings match your search.
        </p>
      ) : (
        <>
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
        </>
      )}
    </div>
  );
}
