"use client";

import { useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { ApiError, apiFetch } from "@/lib/api";

interface Offer {
  id: string;
  name: string;
  description: string;
  active: boolean;
  position: number;
}

const EMPTY_DRAFT = { name: "", description: "" };

/** The storefront's deliberately small editor: offers are words, not prices. */
export default function OffersPage() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<Offer[]>("/api/business/offers")
      .then((rows) => setOffers(rows.filter((row) => row.active)))
      .catch(() => setError("Could not load your offers."));
  }, []);

  useEffect(load, [load]);

  async function save() {
    if (!draft.name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (editing) {
        const saved = await apiFetch<Offer>(`/api/business/offers/${editing}`, {
          method: "PATCH",
          body: JSON.stringify(draft),
        });
        setOffers((rows) => rows.map((row) => (row.id === saved.id ? saved : row)));
      } else {
        const saved = await apiFetch<Offer>("/api/business/offers", {
          method: "POST",
          body: JSON.stringify(draft),
        });
        setOffers((rows) => [...rows, saved]);
      }
      setDraft(EMPTY_DRAFT);
      setEditing(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "That offer could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(offer: Offer) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/business/offers/${offer.id}`, { method: "DELETE" });
      setOffers((rows) => rows.filter((row) => row.id !== offer.id));
      if (editing === offer.id) {
        setEditing(null);
        setDraft(EMPTY_DRAFT);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "That offer could not be removed.");
    } finally {
      setBusy(false);
    }
  }

  function startEdit(offer: Offer) {
    setEditing(offer.id);
    setDraft({ name: offer.name, description: offer.description });
    setError(null);
  }

  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden bg-surface">
      <ScreenTopbar title="What we offer" backHref="/business" />
      <div className="min-h-0 flex-1 overflow-y-auto px-gutter pb-20 pt-5 lg:mx-auto lg:w-full lg:max-w-thread">
        <p className="text-prose text-text-secondary">
          Add the services or offers customers should see on your business page. Prices stay out of
          this page, so customers can ask the agent for the details they need.
        </p>

        <div className="mt-6 rounded-card border border-hairline bg-surface-container p-4">
          <label className="block text-field-label font-medium uppercase text-ink-a40" htmlFor="offer-name">
            Offer name
          </label>
          <input
            id="offer-name"
            value={draft.name}
            onChange={(event) => setDraft((value) => ({ ...value, name: event.target.value }))}
            placeholder="Phone screen repair"
            disabled={busy}
            className="mt-2 w-full rounded-field border border-transparent bg-surface px-3.5 py-3 text-field text-text outline-none focus:border-accent"
          />
          <label className="mt-4 block text-field-label font-medium uppercase text-ink-a40" htmlFor="offer-description">
            Description
          </label>
          <textarea
            id="offer-description"
            value={draft.description}
            onChange={(event) => setDraft((value) => ({ ...value, description: event.target.value }))}
            placeholder="Tell customers what is included."
            disabled={busy}
            rows={3}
            className="mt-2 w-full resize-y rounded-field border border-transparent bg-surface px-3.5 py-3 text-body text-text outline-none focus:border-accent"
          />
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={() => void save()}
              disabled={busy || !draft.name.trim()}
              className="rounded-field bg-accent px-4 py-2.5 text-chip font-medium text-text-inverse disabled:opacity-50"
            >
              {busy ? "Saving…" : editing ? "Save offer" : "Add offer"}
            </button>
            {editing ? (
              <button
                type="button"
                onClick={() => {
                  setEditing(null);
                  setDraft(EMPTY_DRAFT);
                }}
                className="text-chip font-medium text-accent"
              >
                Cancel
              </button>
            ) : null}
          </div>
        </div>

        {error ? <p role="alert" className="mt-3 text-meta text-danger">{error}</p> : null}

        <section className="mt-7">
          <h2 className="text-eyebrow font-medium uppercase text-ink-a40">On your page</h2>
          {offers.length === 0 ? (
            <p className="mt-3 text-prose text-text-secondary">No offers yet.</p>
          ) : (
            <ul className="mt-2 divide-y divide-hairline">
              {offers.map((offer) => (
                <li key={offer.id} className="flex items-start gap-3 py-4">
                  <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-field bg-accent-a09 text-accent">
                    <Icon name="sell" size={16} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-card-hl font-medium text-text">{offer.name}</h3>
                    {offer.description ? <p className="mt-1 text-body-sm text-text-secondary">{offer.description}</p> : null}
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <button type="button" onClick={() => startEdit(offer)} aria-label={`Edit ${offer.name}`} className="flex size-icon-btn items-center justify-center rounded-full text-ink-a40">
                      <Icon name="edit" size={17} />
                    </button>
                    <button type="button" onClick={() => void remove(offer)} aria-label={`Remove ${offer.name}`} className="flex size-icon-btn items-center justify-center rounded-full text-ink-a40">
                      <Icon name="delete" size={17} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
