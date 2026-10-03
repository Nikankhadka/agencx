"use client";
/* eslint-disable @next/next/no-img-element -- storefront cover is a tenant API response. */

import { BrandMark } from "@/components/ui/BrandMark";
import { Icon } from "@/components/ui/Icon";
import type { BusinessProfile } from "@/lib/api-schemas";
import type { StorefrontData } from "@/lib/tenant";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** RF-7: the fields the storefront surfaces an owner edit shortcut for. */
export type OwnerEditField = "name" | "hours" | "description" | "contact";

/** The prototype's `PENCIL_SVG` (12x12, stroked) - the `.edit-btn` glyph. */
const PENCIL_PATH = "M8.5 1.5L10.5 3.5L4 10H2V8L8.5 1.5Z";

/**
 * RF-7: the prototype's circular `.edit-btn` (26px, 1.5px hairline border,
 * muted glyph, accent on hover), one shared control for every shortcut.
 */
export function EditPencil({
  label,
  testId,
  onClick,
}: {
  label: string;
  testId?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      data-testid={testId}
      className="flex size-[26px] shrink-0 items-center justify-center rounded-full border-[1.5px] border-ink-a12 text-ink-a40 transition-colors duration-(--duration-fast) hover:border-accent-a35 hover:text-accent-active active:opacity-60"
    >
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
        <path
          d={PENCIL_PATH}
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}

/**
 * RF-7: the prototype's `.set-field-row` / `.set-edit` settings-row idiom, used
 * for the two fields the storefront does not publish (description, contact).
 * Owner-only - the caller never renders it for a customer.
 */
export function OwnerFieldRow({
  label,
  value,
  placeholder,
  testId,
  editTestId,
  onEdit,
}: {
  label: string;
  value: string;
  placeholder: string;
  testId: string;
  editTestId: string;
  onEdit: () => void;
}) {
  const filled = value.trim().length > 0;
  return (
    <div
      data-testid={testId}
      className="flex items-center justify-between gap-3 border-b border-hairline py-2 last:border-b-0"
    >
      <span className="shrink-0 text-meta text-ink-a40">{label}</span>
      <div className="flex min-w-0 items-center gap-3">
        <span className={`min-w-0 truncate text-body-sm ${filled ? "text-text" : "text-ink-a40"}`}>
          {filled ? value : placeholder}
        </span>
        <button
          type="button"
          onClick={onEdit}
          data-testid={editTestId}
          className="shrink-0 text-chip font-medium text-accent-active transition-opacity duration-(--duration-fast) hover:underline active:opacity-60"
        >
          Edit
        </button>
      </div>
    </div>
  );
}

function linkLabel(key: string) {
  return key === "website" ? "Website" : key.slice(0, 1).toUpperCase() + key.slice(1);
}

/**
 * M-7 hero, amended in founder review to the veil in both states (v4 hero
 * fallback B): no cover renders a 96px `--gradient-veil` band in the cover's
 * place; with a cover the same veil lies over the photo's lower edge so it
 * fades into the page. The monogram overlaps the band the same way in both
 * states, so the composition does not change with media. The subtitle is the
 * owner's `services`, joined into one line (20: it is a list of entries, not a
 * sentence); the legacy combined tagline stays in the payload but is
 * no longer rendered. Long facts wrap instead of truncating (v4 edge case:
 * nothing clipped or ellipsized).
 *
 * RF-7: when `canEdit`, the same hero grows pencil shortcuts beside the name
 * and hours plus an owner-only block for the two unpublished fields. For every
 * other viewer the markup is byte-identical to the shipped customer hero - each
 * owner branch is a separate tree, never an always-present wrapper - so no
 * owner control or contact value can reach a customer.
 */
export function StorefrontHero({
  slug,
  logoUrl,
  storefront,
  canEdit = false,
  profile = null,
  onEdit,
}: {
  slug: string;
  logoUrl?: string;
  storefront: StorefrontData;
  canEdit?: boolean;
  profile?: BusinessProfile | null;
  onEdit?: (field: OwnerEditField) => void;
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
        {canEdit ? (
          <div className="mt-3 flex items-center gap-2">
            <h1 className="min-w-0 wrap-anywhere text-title-1 font-bold text-text">
              {storefront.name}
            </h1>
            <EditPencil
              label="Edit business name"
              testId="owner-edit-name"
              onClick={() => onEdit?.("name")}
            />
          </div>
        ) : (
          <h1 className="mt-3 min-w-0 wrap-anywhere text-title-1 font-bold text-text">
            {storefront.name}
          </h1>
        )}
        {storefront.services?.length ? (
          <p className="mt-2 max-w-prose text-body text-text-secondary">
            {storefront.services.join(", ")}
          </p>
        ) : null}
        {storefront.business_type || storefront.hours ? (
          <div className="mt-3 flex max-w-full flex-wrap gap-2">
            {storefront.business_type ? (
              <span className="inline-flex max-w-full items-center rounded-chip bg-accent-container px-3 py-1 text-chip font-medium text-accent-active">
                <span className="min-w-0 wrap-anywhere">{storefront.business_type}</span>
              </span>
            ) : null}
            {storefront.hours ? (
              canEdit ? (
                <span className="inline-flex max-w-full items-center gap-2">
                  <span className="inline-flex max-w-full items-center rounded-chip bg-surface-container px-3 py-1 text-chip font-medium text-text-secondary">
                    <span className="min-w-0 wrap-anywhere">{storefront.hours}</span>
                  </span>
                  <EditPencil
                    label="Edit opening hours"
                    testId="owner-edit-hours"
                    onClick={() => onEdit?.("hours")}
                  />
                </span>
              ) : (
                <span className="inline-flex max-w-full items-center rounded-chip bg-surface-container px-3 py-1 text-chip font-medium text-text-secondary">
                  <span className="min-w-0 wrap-anywhere">{storefront.hours}</span>
                </span>
              )
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
        {canEdit ? (
          <div data-testid="owner-edit-fields" className="mt-4 max-w-prose">
            <OwnerFieldRow
              label="Description"
              value={profile?.description ?? ""}
              placeholder="Add a short description"
              testId="owner-field-description"
              editTestId="owner-edit-description"
              onEdit={() => onEdit?.("description")}
            />
            <OwnerFieldRow
              label="Business contact"
              value={profile?.business_contact ?? ""}
              placeholder="Add how customers reach you"
              testId="owner-field-contact"
              editTestId="owner-edit-contact"
              onEdit={() => onEdit?.("contact")}
            />
          </div>
        ) : null}
      </section>
    </>
  );
}
