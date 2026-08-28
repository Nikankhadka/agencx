"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { ApiError, apiFetch } from "@/lib/api";

interface Review {
  quote: string;
  author: string;
  source: string;
  rating: number;
}

interface StorefrontSections {
  about: string;
  reviews: Review[];
}

const EMPTY: StorefrontSections = { about: "", reviews: [] };
const EMPTY_REVIEW: Review = { quote: "", author: "", source: "", rating: 5 };

export function StorefrontSectionsEditor() {
  const [sections, setSections] = useState<StorefrontSections>(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // The fields stay disabled until this lands. Enabling them first means an
  // owner who starts typing straight away has their words replaced by the
  // response, silently - a form you cannot type into for a moment is the
  // honest version of one that has not loaded yet.
  useEffect(() => {
    apiFetch<StorefrontSections>("/api/business/storefront")
      .then((current) => {
        setSections(current);
        setLoaded(true);
      })
      .catch(() => setError("Could not load your storefront sections."));
  }, []);

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const next = await apiFetch<StorefrontSections>("/api/business/storefront", {
        method: "PUT",
        body: JSON.stringify(sections),
      });
      setSections(next);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Those changes could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  function updateReview(index: number, patch: Partial<Review>) {
    setSections((current) => ({
      ...current,
      reviews: current.reviews.map((review, itemIndex) =>
        itemIndex === index ? { ...review, ...patch } : review
      ),
    }));
  }

  return (
    <section className="border-t border-hairline px-gutter py-5">
      <h3 className="text-row-label font-medium text-text">About and reviews</h3>
      <p className="mt-1 text-meta text-ink-a40">Write the sections customers see below what you offer.</p>
      <label className="mt-4 block text-field-label font-medium uppercase text-ink-a40" htmlFor="storefront-about">
        About your business
      </label>
      <textarea
        id="storefront-about"
        data-testid="storefront-about"
        value={sections.about}
        onChange={(event) => setSections((current) => ({ ...current, about: event.target.value }))}
        rows={4}
        maxLength={2000}
        disabled={!loaded}
        className="mt-2 w-full resize-y rounded-field border border-transparent bg-surface-container px-3.5 py-3 text-body text-text outline-none focus:border-accent"
      />

      <div className="mt-5 flex items-center justify-between gap-3">
        <h4 className="text-field-label font-medium uppercase text-ink-a40">Reviews</h4>
        <button
          type="button"
          onClick={() => setSections((current) => ({ ...current, reviews: [...current.reviews, EMPTY_REVIEW] }))}
          disabled={!loaded || sections.reviews.length >= 6}
          data-testid="storefront-add-review"
          className="flex items-center gap-1 text-action font-medium text-accent disabled:opacity-50"
        >
          <Icon name="add" size={16} />
          Add review
        </button>
      </div>
      <div className="mt-2 divide-y divide-hairline">
        {sections.reviews.map((review, index) => (
          <div key={index} className="relative py-4 pr-9">
            <label className="block text-field-label font-medium uppercase text-ink-a40" htmlFor={`review-quote-${index}`}>Review</label>
            <textarea
              id={`review-quote-${index}`}
              data-testid="storefront-review-quote"
              value={review.quote}
              onChange={(event) => updateReview(index, { quote: event.target.value })}
              rows={2}
              maxLength={500}
              className="mt-2 w-full resize-y rounded-field border border-transparent bg-surface-container px-3 py-2.5 text-body-sm text-text outline-none focus:border-accent"
            />
            <div className="mt-2 grid grid-cols-2 gap-2">
              <input data-testid="storefront-review-author" value={review.author} onChange={(event) => updateReview(index, { author: event.target.value })} placeholder="Customer name" maxLength={120} className="min-w-0 rounded-field bg-surface-container px-3 py-2.5 text-body-sm text-text outline-none focus:ring-1 focus:ring-accent" />
              <input value={review.source} onChange={(event) => updateReview(index, { source: event.target.value })} placeholder="Source, optional" maxLength={120} className="min-w-0 rounded-field bg-surface-container px-3 py-2.5 text-body-sm text-text outline-none focus:ring-1 focus:ring-accent" />
            </div>
            <button type="button" onClick={() => setSections((current) => ({ ...current, reviews: current.reviews.filter((_, itemIndex) => itemIndex !== index) }))} aria-label="Remove review" className="absolute right-0 top-8 flex size-icon-btn items-center justify-center rounded-full text-ink-a40">
              <Icon name="delete" size={17} />
            </button>
          </div>
        ))}
      </div>
      {error ? <p role="alert" className="mt-3 text-meta text-danger">{error}</p> : null}
      <button type="button" data-testid="storefront-save" onClick={() => void save()} disabled={!loaded || busy} className="mt-5 rounded-field bg-accent px-4 py-2.5 text-chip font-medium text-text-inverse disabled:opacity-50">
        {busy ? "Saving…" : saved ? "Saved" : "Save page sections"}
      </button>
    </section>
  );
}
