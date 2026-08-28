"use client";

import { useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";

interface StorefrontSections {
  about: string;
}

const EMPTY: StorefrontSections = { about: "" };

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

  return (
    <section className="border-t border-hairline px-gutter py-5">
      <h3 className="text-row-label font-medium text-text">About your business</h3>
      <p className="mt-1 text-meta text-ink-a40">Write the section customers see below what you offer.</p>
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

      {error ? <p role="alert" className="mt-3 text-meta text-danger">{error}</p> : null}
      <button type="button" data-testid="storefront-save" onClick={() => void save()} disabled={!loaded || busy} className="mt-5 rounded-field bg-accent px-4 py-2.5 text-chip font-medium text-text-inverse disabled:opacity-50">
        {busy ? "Saving…" : saved ? "Saved" : "Save page sections"}
      </button>
    </section>
  );
}
