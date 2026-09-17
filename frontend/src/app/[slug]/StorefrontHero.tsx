/* eslint-disable @next/next/no-img-element -- storefront cover is a tenant API response. */

import { BrandMark } from "@/components/ui/BrandMark";
import { Icon } from "@/components/ui/Icon";
import type { StorefrontData } from "@/lib/tenant";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function linkLabel(key: string) {
  return key === "website" ? "Website" : key.slice(0, 1).toUpperCase() + key.slice(1);
}

/**
 * M-7 hero, amended in founder review to the veil in both states (v4 hero
 * fallback B): no cover renders a 96px `--gradient-veil` band in the cover's
 * place; with a cover the same veil lies over the photo's lower edge so it
 * fades into the page. The monogram overlaps the band the same way in both
 * states, so the composition does not change with media. The subtitle is the
 * owner's `services`; the legacy combined tagline stays in the payload but is
 * no longer rendered. Long facts wrap instead of truncating (v4 edge case:
 * nothing clipped or ellipsized).
 */
export function StorefrontHero({
  slug,
  logoUrl,
  storefront,
}: {
  slug: string;
  logoUrl?: string;
  storefront: StorefrontData;
}) {
  return (
    <>
      {storefront.has_cover ? (
        <div className="relative">
          <img
            src={storefront.cover_url || `${API_URL}/api/public/tenant/${encodeURIComponent(slug)}/cover`}
            alt=""
            fetchPriority="high"
            className="h-40 w-full object-cover md:h-80 md:rounded-lg"
          />
          <div
            aria-hidden
            data-testid="hero-veil"
            className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-veil md:rounded-b-lg"
          />
        </div>
      ) : (
        <div aria-hidden data-testid="hero-veil" className="h-24 w-full bg-veil md:rounded-lg" />
      )}

      <section className="relative px-gutter pb-6 pt-5">
        {/* Block-level, not inline: a negative top margin only shifts a
            block-level box, and the overlap is the whole point of the band. */}
        <div data-testid="hero-mark" className="-mt-12 flex w-fit rounded-full ring-4 ring-surface">
          <BrandMark logoUrl={logoUrl} name={storefront.name} size="lg" />
        </div>
        <h1 className="mt-3 min-w-0 wrap-anywhere text-title-1 font-bold text-text">
          {storefront.name}
        </h1>
        {storefront.services ? (
          <p className="mt-2 max-w-prose text-body text-text-secondary">{storefront.services}</p>
        ) : null}
        {storefront.business_type || storefront.hours ? (
          <div className="mt-3 flex max-w-full flex-wrap gap-2">
            {storefront.business_type ? (
              <span className="inline-flex max-w-full items-center rounded-chip bg-accent-container px-3 py-1 text-chip font-medium text-accent-active">
                <span className="min-w-0 wrap-anywhere">{storefront.business_type}</span>
              </span>
            ) : null}
            {storefront.hours ? (
              <span className="inline-flex max-w-full items-center rounded-chip bg-surface-container px-3 py-1 text-chip font-medium text-text-secondary">
                <span className="min-w-0 wrap-anywhere">{storefront.hours}</span>
              </span>
            ) : null}
          </div>
        ) : null}
        {Object.keys(storefront.links).length > 0 ? (
          <nav aria-label={`${storefront.name} links`} className="mt-4 flex flex-wrap gap-2">
            {Object.entries(storefront.links).map(([key, href]) => (
              <a
                key={key}
                href={href}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-11 items-center gap-2 whitespace-nowrap rounded-chip border border-border px-3 text-chip font-medium text-text transition-colors duration-(--duration-fast) hover:bg-surface-container active:bg-surface-container-high"
              >
                {linkLabel(key)}
                <Icon name="open_in_new" size={13} />
              </a>
            ))}
          </nav>
        ) : null}
      </section>
    </>
  );
}
