"use client";

import { useEffect, useState } from "react";
import { toast } from "react-hot-toast";
import { ReviewSheet } from "./ReviewSheet";
import type { PendingOffering, ReviewOffering } from "./types";
import { ApiError, apiFetch } from "@/lib/api";

interface SuggestionsResponse {
  count: number;
  candidates: ReviewOffering[];
}

interface OfferingSuggestionsProps {
  variant: "card" | "section";
}

export function OfferingSuggestions({ variant }: OfferingSuggestionsProps) {
  const [data, setData] = useState<SuggestionsResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch<SuggestionsResponse>("/api/onboarding/suggestions")
      .then(setData)
      .catch(() => setData(null));
  }, []);

  if (!data || data.count === 0) return null;

  async function save(candidates: PendingOffering[]) {
    setBusy(true);
    try {
      const next = await apiFetch<SuggestionsResponse>("/api/onboarding/suggestions", {
        method: "PUT",
        body: JSON.stringify({ candidates }),
      });
      setData(next);
      setOpen(false);
      toast.success("Suggestions saved");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.detail : "Couldn't save suggestions.");
    } finally {
      setBusy(false);
    }
  }

  const trigger = variant === "card" ? (
    <article className="mt-4 rounded-card border border-hairline bg-surface p-4 shadow-card">
      <p className="text-card-hl font-medium text-text">
        {data.count} {data.count === 1 ? "offering" : "offerings"} waiting for review
      </p>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-3 rounded-chip border-chip border-accent-a28 px-4 py-2 text-chip text-accent-active transition-colors duration-(--duration-fast) hover:bg-accent-a07 active:bg-accent-a07"
      >
        Review suggestions
      </button>
    </article>
  ) : (
    <section className="border-b border-hairline px-gutter py-4" aria-labelledby="suggestions-heading">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 id="suggestions-heading" className="text-row-label font-medium text-text">
            Suggestions to review
          </h2>
          <p className="mt-1 text-meta text-ink-a40">
            {data.count} private {data.count === 1 ? "draft" : "drafts"} from onboarding.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="shrink-0 text-action font-medium text-accent-active transition-colors duration-(--duration-fast) hover:underline active:opacity-60"
        >
          Review
        </button>
      </div>
    </section>
  );

  return (
    <>
      {trigger}
      <ReviewSheet
        workspace={null}
        suggestions={data.candidates}
        suggestionsOnly
        open={open}
        busy={busy}
        priceConflict={null}
        onClose={() => setOpen(false)}
        onSave={async () => null}
        onSaveSuggestions={save}
        onDiscard={() => setOpen(false)}
      />
    </>
  );
}
