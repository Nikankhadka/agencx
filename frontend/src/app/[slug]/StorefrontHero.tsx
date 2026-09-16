/* eslint-disable @next/next/no-img-element -- storefront cover is a tenant API response. */

import { BrandMark } from "@/components/ui/BrandMark";
import { Icon } from "@/components/ui/Icon";
import type { StorefrontData } from "@/lib/tenant";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function linkLabel(key: string) {
  return key === "website" ? "Website" : key.slice(0, 1).toUpperCase() + key.slice(1);
}

/**
 * M-7 plain-identity hero (v4 frame 1): the monogram, name, and facts lead -
 * there is no reserved cover band, so the no-photo state is the base
 * foundation rather than an empty state. With a cover the large mark overlaps
 * it; without one the identity stands on its own. The subtitle is the owner's
 * `services`; the legacy combined tagline stays in the payload but is no
 * longer rendered. Fact chips truncate instead of breaking the row (v4 edge
 * case: stretched profile strings).
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
        <img
          src={storefront.cover_url || `${API_URL}/api/public/tenant/${encodeURIComponent(slug)}/cover`}
          alt=""
          fetchPriority="high"
          className="h-40 w-full object-cover md:h-80 md:rounded-lg"
        />
      ) : null}

      <section className="px-gutter pb-6 pt-5">
        {storefront.has_cover ? (
          <span className="-mt-12 inline-flex rounded-full ring-4 ring-surface">
            <BrandMark logoUrl={logoUrl} name={storefront.name} size="lg" />
          </span>
        ) : (
          <BrandMark logoUrl={logoUrl} name={storefront.name} size="lg" />
        )}
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
                <span className="min-w-0 truncate">{storefront.business_type}</span>
              </span>
            ) : null}
            {storefront.hours ? (
              <span className="inline-flex max-w-full items-center rounded-chip bg-surface-container px-3 py-1 text-chip font-medium text-text-secondary">
                <span className="min-w-0 truncate">{storefront.hours}</span>
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
