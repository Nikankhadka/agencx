"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { ApiError, apiFetch } from "@/lib/api";

interface Offering {
  id: string;
  name: string;
  description: string;
  price_cents: number | null;
}

interface FormValues {
  name: string;
  description: string;
  price: string;
}

const EMPTY_FORM: FormValues = { name: "", description: "", price: "" };

function formFor(offering: Offering): FormValues {
  return {
    name: offering.name,
    description: offering.description,
    price:
      offering.price_cents === null
        ? ""
        : (offering.price_cents / 100).toFixed(2),
  };
}

export function OfferingsList() {
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [form, setForm] = useState<FormValues>(EMPTY_FORM);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setOfferings(await apiFetch<Offering[]>("/api/business/offerings"));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load what you offer.");
    }
  }

  useEffect(() => {
    apiFetch<Offering[]>("/api/business/offerings")
      .then(setOfferings)
      .catch((err) =>
        setError(err instanceof ApiError ? err.detail : "Couldn't load what you offer."),
      );
  }, []);

  function begin(offering?: Offering) {
    setError(null);
    setEditing(offering?.id ?? "new");
    setForm(offering ? formFor(offering) : EMPTY_FORM);
  }

  function close() {
    if (!working) setEditing(null);
  }

  async function save() {
    if (!editing || !form.name.trim()) return;
    setWorking(true);
    setError(null);
    const body = {
      name: form.name,
      description: form.description,
      price_dollars: form.price.trim() || null,
    };
    try {
      const path = editing === "new" ? "/api/business/offerings" : `/api/business/offerings/${editing}`;
      await apiFetch<Offering>(path, {
        method: editing === "new" ? "POST" : "PATCH",
        body: JSON.stringify(body),
      });
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't save that offering.");
    } finally {
      setWorking(false);
    }
  }

  async function remove(offering: Offering) {
    if (working || !window.confirm(`Remove ${offering.name}?`)) return;
    setWorking(true);
    setError(null);
    try {
      await apiFetch(`/api/business/offerings/${offering.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't remove that offering.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className="border-b border-hairline px-gutter py-5" aria-labelledby="offerings-heading">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="offerings-heading" className="text-row-label font-medium text-text">
            What you offer
          </h2>
          <p className="mt-1 text-meta text-ink-a40">
            Add the services or products customers can ask about.
          </p>
        </div>
        {editing === null ? (
          <button
            type="button"
            onClick={() => begin()}
            data-testid="offering-add"
            className="flex shrink-0 items-center gap-1 text-action font-medium text-accent active:opacity-60"
          >
            <Icon name="add" size={16} />
            Add
          </button>
        ) : null}
      </div>

      {offerings.length > 0 ? (
        <ul className="mt-3 divide-y divide-hairline" data-testid="offerings-list">
          {offerings.map((offering) => (
            <li key={offering.id} className="flex items-center gap-3 py-3">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-card-hl font-medium text-text">{offering.name}</span>
                {offering.description ? (
                  <span className="mt-0.5 block truncate text-meta text-ink-a40">
                    {offering.description}
                  </span>
                ) : null}
                {offering.price_cents !== null ? (
                  <span className="mt-0.5 block text-meta text-ink-a40">
                    ${(offering.price_cents / 100).toFixed(2)}
                  </span>
                ) : null}
              </span>
              <button
                type="button"
                onClick={() => begin(offering)}
                disabled={working}
                aria-label={`Edit ${offering.name}`}
                data-testid="offering-edit"
                className="flex size-icon-btn shrink-0 items-center justify-center rounded-full text-ink-a40 active:opacity-60 disabled:opacity-50"
              >
                <Icon name="edit" size={18} />
              </button>
              <button
                type="button"
                onClick={() => void remove(offering)}
                disabled={working}
                aria-label={`Remove ${offering.name}`}
                data-testid="offering-remove"
                className="flex size-icon-btn shrink-0 items-center justify-center rounded-full text-ink-a40 active:opacity-60 disabled:opacity-50"
              >
                <Icon name="delete" size={18} />
              </button>
            </li>
          ))}
        </ul>
      ) : editing === null ? (
        <p className="mt-3 text-prose text-ink-a40">Nothing added yet.</p>
      ) : null}

      {editing !== null ? (
        <form
          className="mt-4 rounded-card bg-accent-a06 p-4"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <label className="block text-field-label font-medium uppercase text-ink-a40">
            Name
            <input
              autoFocus
              required
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              data-testid="offering-name"
              className="mt-1.5 w-full rounded-field border-[length:var(--border-chip)] border-transparent bg-surface px-3.5 py-3 text-field text-text outline-none focus:border-accent-a35"
            />
          </label>
          <label className="mt-3 block text-field-label font-medium uppercase text-ink-a40">
            Description <span className="normal-case">(optional)</span>
            <input
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              data-testid="offering-description"
              className="mt-1.5 w-full rounded-field border-[length:var(--border-chip)] border-transparent bg-surface px-3.5 py-3 text-field text-text outline-none focus:border-accent-a35"
            />
          </label>
          <label className="mt-3 block text-field-label font-medium uppercase text-ink-a40">
            Price <span className="normal-case">(optional)</span>
            <input
              value={form.price}
              onChange={(event) => setForm((current) => ({ ...current, price: event.target.value }))}
              inputMode="decimal"
              placeholder="0.00"
              data-testid="offering-price"
              className="mt-1.5 w-full rounded-field border-[length:var(--border-chip)] border-transparent bg-surface px-3.5 py-3 text-field text-text outline-none focus:border-accent-a35"
            />
          </label>
          {error ? <p className="mt-2 text-meta text-danger">{error}</p> : null}
          <div className="mt-4 flex justify-end gap-3">
            <button type="button" onClick={close} disabled={working} className="text-action text-ink-a40">
              Cancel
            </button>
            <button
              type="submit"
              disabled={working || !form.name.trim()}
              data-testid="offering-save"
              className="rounded-field bg-accent px-4 py-2 text-action font-medium text-text-inverse disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </form>
      ) : error ? (
        <p className="mt-3 text-meta text-danger">{error}</p>
      ) : null}
    </section>
  );
}
