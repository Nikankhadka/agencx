"use client";

import { useMemo, useState } from "react";
import { Icon } from "@/components/ui/Icon";

export interface CategoryOption {
  id: string;
  name: string;
  normalized_key?: string;
  offering_count?: number;
}

interface Props {
  categories: CategoryOption[];
  selectedIds: string[];
  primaryId: string | null;
  onChange: (selectedIds: string[], primaryId: string | null) => void;
  onCreate: (name: string) => Promise<CategoryOption>;
  label?: string;
}

export function normalizedCategoryName(value: string) {
  return value
    .normalize("NFKC")
    .trim()
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function splitCategoryNames(value: string) {
  return [...new Set(value.split(/[\/,;&]+/).map((part) => part.trim()).filter(Boolean))];
}

export function CategoryPicker({
  categories,
  selectedIds,
  primaryId,
  onChange,
  onCreate,
  label = "Categories",
}: Props) {
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const selected = selectedIds
    .map((id) => categories.find((category) => category.id === id))
    .filter((category): category is CategoryOption => Boolean(category));
  const matches = useMemo(() => {
    const needle = normalizedCategoryName(query);
    return categories.filter(
      (category) =>
        !selectedIds.includes(category.id) && normalizedCategoryName(category.name).includes(needle),
    );
  }, [categories, query, selectedIds]);
  const exact = categories.find(
    (category) => normalizedCategoryName(category.name) === normalizedCategoryName(query),
  );
  const parts = splitCategoryNames(query);

  function select(category: CategoryOption) {
    const next = [...selectedIds, category.id];
    onChange(next, primaryId ?? category.id);
    setQuery("");
  }

  function remove(id: string) {
    const next = selectedIds.filter((selectedId) => selectedId !== id);
    onChange(next, primaryId === id ? (next[0] ?? null) : primaryId);
  }

  async function create(names: string[]) {
    if (creating) return;
    setCreating(true);
    setCreateError(null);
    try {
      const nextIds = [...selectedIds];
      for (const name of names) {
        const found = categories.find(
          (category) => normalizedCategoryName(category.name) === normalizedCategoryName(name),
        );
        const category = found ?? (await onCreate(name));
        if (!nextIds.includes(category.id)) nextIds.push(category.id);
      }
      onChange(nextIds, primaryId ?? nextIds[0] ?? null);
      setQuery("");
    } catch {
      setCreateError("Couldn't create that category.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <fieldset>
      <legend className="text-label font-medium uppercase text-ink-a40">{label}</legend>
      {selected.length ? (
        <ul className="mt-2 flex flex-wrap gap-2" aria-label="Selected categories">
          {selected.map((category) => (
            <li
              key={category.id}
              className="flex items-center gap-1 rounded-full bg-surface-container px-2 py-1 text-meta text-text"
            >
              <button
                type="button"
                onClick={() => onChange(selectedIds, category.id)}
                aria-label={`Make ${category.name} primary`}
                aria-pressed={primaryId === category.id}
                className="font-medium text-accent-active"
              >
                {primaryId === category.id ? "Primary" : "Make primary"}
              </button>
              <span>{category.name}</span>
              <button
                type="button"
                onClick={() => remove(category.id)}
                aria-label={`Remove ${category.name}`}
                className="rounded-full p-1 text-ink-a40 hover:text-text"
              >
                <Icon name="cancel" size={14} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-meta text-ink-a40">No category selected.</p>
      )}
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search or create a category"
        aria-label="Search categories"
        className="mt-2 w-full rounded-field border border-border bg-surface px-3 py-2 text-field text-text outline-none placeholder:text-ink-a40 focus:border-text"
      />
      {query.trim() ? (
        <div className="mt-2 rounded-field border border-hairline bg-surface p-2">
          {matches.slice(0, 6).map((category) => (
            <button
              key={category.id}
              type="button"
              onClick={() => select(category)}
              className="block w-full rounded-field px-2 py-2 text-left text-field text-text hover:bg-surface-container"
            >
              {category.name}
            </button>
          ))}
          {!exact && parts.length > 1 ? (
            <button
              type="button"
              disabled={creating}
              onClick={() => void create(parts)}
              className="block w-full rounded-field px-2 py-2 text-left text-field font-medium text-accent-active hover:bg-surface-container disabled:opacity-50"
            >
              Create separately: {parts.join(", ")}
            </button>
          ) : null}
          {!exact ? (
            <button
              type="button"
              disabled={creating}
              onClick={() => void create([query.trim()])}
              className="block w-full rounded-field px-2 py-2 text-left text-field font-medium text-accent-active hover:bg-surface-container disabled:opacity-50"
            >
              {parts.length > 1 ? `Keep exact label: ${query.trim()}` : `Create ${query.trim()}`}
            </button>
          ) : null}
        </div>
      ) : null}
      {createError ? <p className="mt-2 text-meta text-danger">{createError}</p> : null}
      <p className="mt-2 text-meta text-ink-a40">
        Categories help customers browse. Select only the ones that genuinely fit.
      </p>
    </fieldset>
  );
}
