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

function videoEmbedUrl(provider: string, rawUrl: string): string | null {
  try {
    const parsed = new URL(rawUrl);
    const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
    if (provider === "youtube" && (host === "youtube.com" || host === "youtube-nocookie.com" || host === "youtu.be")) {
      const id = host === "youtu.be"
        ? parsed.pathname.split("/").filter(Boolean)[0]
        : parsed.searchParams.get("v") || parsed.pathname.match(/^\/(?:embed|shorts)\/([^/]+)/)?.[1];
      return id ? `https://www.youtube-nocookie.com/embed/${encodeURIComponent(id)}?rel=0` : null;
    }
    if (provider === "vimeo" && (host === "vimeo.com" || host === "player.vimeo.com")) {
      const id = parsed.pathname.match(/\/(?:video\/)?(\d+)(?:\/|$)/)?.[1];
      return id ? `https://player.vimeo.com/video/${id}?title=0` : null;
    }
  } catch {
    return null;
  }
  return null;
}

function VideoMedia({ media }: { media: NonNullable<StorefrontData["offerings"][number]["media"]> }) {
  if (media.provider === "cloudinary") {
    return (
      <video
        controls
        preload="metadata"
        poster={media.poster_url ?? undefined}
        className="max-h-72 w-full rounded-card bg-surface-container object-contain"
      >
        <source src={media.url} />
        Your browser does not support this video.
      </video>
    );
  }
  const embed = videoEmbedUrl(media.provider, media.url);
  if (embed) {
    return (
      <iframe
        src={embed}
        title="Offering video"
        loading="lazy"
        allow="fullscreen; picture-in-picture"
        className="aspect-video w-full rounded-card border-0 bg-surface-container"
      />
    );
  }
  return (
    <a href={media.url} target="_blank" rel="noreferrer" className="block rounded-card bg-surface-container p-6 text-center text-action text-accent">
      Open video
    </a>
  );
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
  const [selected, setSelected] = useState<StorefrontData["offerings"][number] | null>(null);
  const composerRef = useRef<((text: string) => void) | null>(null);
  const [shared, setShared] = useState(false);
  async function share() {
    const url = typeof window === "undefined" ? `/${slug}` : window.location.href;
    try {
      if (typeof navigator.share === "function") {
        await navigator.share({ title: storefront.name, url });
      } else {
        await navigator.clipboard.writeText(url);
      }
      setShared(true);
      window.setTimeout(() => setShared(false), 2000);
    } catch {
      // A cancelled native share is not an error state.
    }
  }
  function openChat() {
    setChatOpen(true);
  }
  const categories = Array.from(new Set(storefront.offerings.map((item) => item.category).filter(Boolean))) as string[];
  const hasUncategorized = storefront.offerings.some((item) => !item.category);
  const groupedCategories = categories.length > 1 ? [...categories, ...(hasUncategorized ? ["More"] : [])] : ["More"];

  return (
    <main className="mx-auto min-h-dvh w-full max-w-[720px] bg-surface pb-8">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface/95 px-gutter py-3 backdrop-blur">
        <div className="flex min-w-0 items-center gap-2.5">
          <BrandMark logoUrl={logoUrl} name={storefront.name} />
          <span className="truncate text-title-3 font-semibold text-text">{storefront.name}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button type="button" onClick={() => void share()} className="rounded-chip border border-border px-3 py-2 text-chip font-medium text-text">
            {shared ? "Copied" : "Share"}
          </button>
          <button
            type="button"
            onClick={() => openChat()}
            className="flex items-center gap-1.5 rounded-chip bg-accent px-3 py-2 text-chip font-medium text-text-inverse active:opacity-85"
          >
            <Icon name="forum" size={15} />
            Ask a question
          </button>
        </div>
      </header>

      {storefront.has_cover ? (
        <img
          src={storefront.cover_url || `${API_URL}/api/public/tenant/${encodeURIComponent(slug)}/cover`}
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
      </section>

      {storefront.offerings.length > 0 ? (
        <section className="border-t border-hairline px-gutter py-7">
          {categories.length > 1 ? (
            <nav aria-label="Offer categories" className="-mx-gutter mb-4 flex gap-2 overflow-x-auto px-gutter pb-1">
              {groupedCategories.map((category) => <span key={category} className="shrink-0 rounded-chip bg-surface-container px-3 py-1.5 text-chip text-text-secondary">{category}</span>)}
            </nav>
          ) : null}
          {groupedCategories.map((category) => (
            <div key={category} className="mb-6 last:mb-0">
              <h2 className="text-title-2 font-semibold text-text">{categories.length <= 1 ? "What we offer" : category}</h2>
              <div className="mt-4 divide-y divide-hairline rounded-card border border-hairline bg-surface">
            {storefront.offerings.filter((item) => categories.length <= 1 || (item.category || "More") === category).map((offering) => (
              <button key={offering.id} type="button" onClick={() => setSelected(offering)} className="block w-full p-4 text-left hover:bg-surface-container">
                {offering.media?.type === "image" ? (
                  <img src={offering.media.url} alt="" className="mb-3 h-32 w-full rounded-field object-cover" />
                ) : offering.media?.type === "video" ? (
                  offering.media.poster_url ? (
                    <div className="relative mb-3">
                      <img src={offering.media.poster_url} alt="" className="h-32 w-full rounded-field object-cover" />
                      <span className="absolute bottom-2 left-2 rounded-chip bg-scrim px-2 py-1 text-meta text-text-inverse">Video</span>
                    </div>
                  ) : (
                    <div className="mb-3 rounded-field bg-surface-container p-3 text-meta text-text-secondary">Video</div>
                  )
                ) : null}
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
              </button>
            ))}
              </div>
            </div>
          ))}
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

      <footer className="border-t border-hairline px-gutter py-5 text-center text-meta text-text-tertiary">
        Powered by Agencx
      </footer>

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
            composerRef={composerRef}
          />
        </div>
      </Sheet>
      <Sheet open={selected !== null} onClose={() => setSelected(null)} title={selected?.name ?? "Offering details"}>
        {selected ? (
          <div className="space-y-4 p-5">
            {selected.media?.type === "image" ? (
              <img src={selected.media.url} alt="" className="max-h-72 w-full rounded-card object-cover" />
            ) : selected.media?.type === "video" ? (
              <VideoMedia media={selected.media} />
            ) : null}
            {selected.description ? <p className="text-prose text-text-secondary">{selected.description}</p> : null}
            {selected.price_cents !== null ? <p className="text-title-2 font-semibold text-text">{priceLabel(selected.price_cents)}</p> : null}
            <button type="button" onClick={() => { setChatOpen(true); composerRef.current?.(`Tell me about ${selected.name}`); setSelected(null); }} className="w-full rounded-field bg-accent px-4 py-3 text-action font-medium text-text-inverse">Ask about this</button>
          </div>
        ) : null}
      </Sheet>
    </main>
  );
}
