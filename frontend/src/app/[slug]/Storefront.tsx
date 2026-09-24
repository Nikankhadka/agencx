"use client";
/* eslint-disable @next/next/no-img-element -- storefront cover is a tenant API response. */

import { useRef, useState } from "react";
import { BrandMark } from "@/components/ui/BrandMark";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { ServicesOverview } from "@/components/ui/ServicesOverview";
import { Sheet } from "@/components/ui/Sheet";
import type { StorefrontData } from "@/lib/tenant";
import { CustomerChat } from "./CustomerChat";
import { Offerings, priceLabel } from "./Offerings";
import { StorefrontHero } from "./StorefrontHero";

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
    <a href={media.url} target="_blank" rel="noreferrer" className="block rounded-card bg-surface-container p-6 text-center text-action text-accent-active transition-[filter] duration-(--duration-fast) hover:brightness-95 active:brightness-90">
      Open video
    </a>
  );
}

function SheetImage({ src }: { src: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return (
    <img
      src={src}
      alt=""
      onError={() => setFailed(true)}
      className="max-h-72 w-full rounded-card object-cover"
    />
  );
}

/**
 * M-7 minimal business (v4 frames 5a/5b): no offerings is never an empty
 * state. The page shows the name, description, and facts, and the assistant's
 * invitation uses the remaining page - the sakura wash lives only behind the
 * assistant's card, never the hero.
 */
function AssistantInvite({ name, onChat }: { name: string; onChat: () => void }) {
  return (
    <div className="flex flex-1 items-center px-gutter py-8">
      <div className="w-full rounded-card bg-accent-a09 p-5">
        <div className="flex items-start gap-3">
          <BrandMark name={name} />
          <p className="flex-1 rounded-card bg-surface px-4 py-3 text-body text-text">
            Hi, I&apos;m {name}&apos;s assistant. Ask me anything - what we do, what we
            charge, or a time that suits you.
          </p>
        </div>
        <button
          type="button"
          onClick={onChat}
          className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-chip bg-accent px-4 py-2 text-action font-medium text-text-inverse transition-colors duration-(--duration-fast) hover:bg-accent-hover active:bg-accent-active"
        >
          Reply
          <Icon name="arrow_forward" size={16} />
        </button>
      </div>
    </div>
  );
}

function scrollTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
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
  const hasOfferings = storefront.offerings.length > 0;

  return (
    <main className="flex min-h-dvh w-full flex-col bg-surface pb-8">
      <header className="sticky top-0 z-10 h-16 border-b border-hairline bg-surface/95 backdrop-blur">
        <Container width="wide" className="flex h-full items-center justify-between">
          <button
            type="button"
            onClick={scrollTop}
            aria-label="Back to top"
            title="Back to top"
            className="-ml-2 flex min-h-11 min-w-0 items-center gap-3 rounded-field px-2 py-1 text-left transition-colors duration-(--duration-fast) hover:bg-surface-container active:bg-surface-container-high"
          >
            <BrandMark logoUrl={logoUrl} name={storefront.name} />
            <span className="truncate text-title-3 font-semibold text-text">{storefront.name}</span>
          </button>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => void share()}
              aria-label={shared ? "Link copied" : "Share page"}
              title={shared ? "Link copied" : "Share page"}
              className="grid size-11 place-items-center rounded-full border border-border text-text transition-colors duration-(--duration-fast) hover:bg-surface-container active:bg-surface-container-high"
            >
              <Icon name={shared ? "check_circle" : "share"} size={20} />
            </button>
            <button
              type="button"
              onClick={openChat}
              aria-label={`Chat with ${storefront.name}`}
              title={`Chat with ${storefront.name}`}
              className="grid size-11 place-items-center rounded-full bg-accent text-text-inverse transition-colors duration-(--duration-fast) hover:bg-accent-hover active:bg-accent-active"
            >
              <Icon name="forum" size={20} />
            </button>
          </div>
        </Container>
      </header>

      {hasOfferings ? (
        <>
          <div className="mx-auto w-full max-w-5xl md:px-gutter md:pt-6">
            <StorefrontHero slug={slug} logoUrl={logoUrl} storefront={storefront} />
          </div>
          <Offerings offerings={storefront.offerings} onSelect={setSelected} />
        </>
      ) : (
        <div className="flex flex-1 flex-col">
          <div className="mx-auto w-full max-w-5xl md:px-gutter md:pt-6">
            <StorefrontHero slug={slug} logoUrl={logoUrl} storefront={storefront} />
          </div>
          {/* 20: with no catalog the overview is all the page can say about
              what this business does, so it renders here rather than leaving
              the question to the assistant alone. */}
          <ServicesOverview
            services={storefront.services ?? []}
            className="mx-auto w-full max-w-5xl px-gutter"
          />
          <AssistantInvite name={storefront.name} onChat={openChat} />
        </div>
      )}

      <footer className="mx-auto mt-auto flex w-full max-w-5xl items-center justify-between border-t border-hairline px-gutter py-6 text-meta text-text-tertiary">
        <span className="font-medium text-text">Agencx</span>
        <span>Powered by Agencx</span>
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
              <SheetImage key={selected.media.url} src={selected.media.url} />
            ) : selected.media?.type === "video" ? (
              <VideoMedia media={selected.media} />
            ) : null}
            {selected.description ? <p className="text-prose text-text-secondary">{selected.description}</p> : null}
            {selected.price_cents !== null ? <p className="text-title-2 font-semibold text-text">{priceLabel(selected.price_cents)}</p> : null}
            <button type="button" onClick={() => { setChatOpen(true); composerRef.current?.(`Tell me about ${selected.name}`); setSelected(null); }} className="w-full rounded-field bg-brand px-4 py-3 text-action font-medium text-text-inverse hover:brightness-95 active:brightness-90">Ask about this</button>
          </div>
        ) : null}
      </Sheet>
    </main>
  );
}
