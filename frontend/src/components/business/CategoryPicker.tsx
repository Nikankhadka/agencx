"use client";

import { useMemo, useRef, useState, type ReactNode } from "react";
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
  /** 31: focus the search field on mount - the review's collapsed picker is
   *  opened by a trigger, so the owner lands in the field they came for. */
  focusSearch?: boolean;
  /** 31: the review renders the picker inside its own named panel, so the
   *  duplicate heading and the onboarding hint are dropped there. The
   *  Business form keeps both: it has no panel to name the group. */
  compact?: boolean;
  /** 31: a control rendered beside the search field - the review's Done. */
  action?: ReactNode;
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
  focusSearch = false,
  compact = false,
  action,
}: Props) {
  const searchRef = useRef<HTMLInputElement>(null);
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
      <legend
        className={
          compact
            ? "sr-only"
            : "text-label font-medium uppercase text-ink-a40"
        }
      >
        {label}
      </legend>
      {selected.length ? (
        <ul className="mt-2 flex flex-wrap gap-2" aria-label="Selected categories">
          {selected.map((category) => {
            const primary = primaryId === category.id;
            return (
              <li
                key={category.id}
                className={`flex min-h-11 items-center rounded-full border pl-3 text-body-sm font-medium ${
                  primary
                    ? "border-transparent bg-accent-container text-accent-active"
                    : "border-border bg-surface text-text"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onChange(selectedIds, category.id)}
                  aria-label={`Make ${category.name} primary`}
                  aria-pressed={primary}
                  className="flex min-h-11 min-w-0 items-center gap-2 transition-opacity duration-(--duration-fast) hover:opacity-80 active:opacity-60"
                >
                  {primary ? (
                    <Icon name="check" size={14} className="shrink-0" />
                  ) : null}
                  <span className="truncate">{category.name}</span>
                </button>
                <button
                  type="button"
                  onClick={() => remove(category.id)}
                  aria-label={`Remove ${category.name}`}
                  className={`grid size-11 shrink-0 place-items-center rounded-full transition-opacity duration-(--duration-fast) hover:opacity-70 active:opacity-60 ${
                    primary ? "text-accent-active" : "text-text-secondary"
                  }`}
                >
                  <Icon name="close" size={14} />
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
      <div className={action ? "mt-2 flex items-center gap-2" : undefined}>
        <input
          ref={searchRef}
          autoFocus={focusSearch}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search or create a category"
          aria-label="Search categories"
          className={`${action ? "min-w-0 flex-1" : "mt-2 w-full"} rounded-field border border-border bg-surface px-4 py-3 text-body text-text min-h-11 outline-none placeholder:text-ink-a40 focus:border-text`}
        />
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {query.trim() ? (
        <div
          className={
            compact
              ? "mt-1"
              : "mt-2 rounded-field border border-hairline bg-surface p-2"
          }
        >
          {matches.slice(0, 6).map((category) => (
            <button
              key={category.id}
              type="button"
              onClick={() => select(category)}
              className="block min-h-11 w-full rounded-field px-4 py-2 text-left text-body text-text transition-colors duration-(--duration-fast) hover:bg-surface-container"
            >
              {category.name}
            </button>
          ))}
          {!exact && parts.length > 1 ? (
            <button
              type="button"
              disabled={creating}
              onClick={() => void create(parts)}
              className="block min-h-11 w-full rounded-field px-4 py-2 text-left text-body font-medium text-accent-active transition-colors duration-(--duration-fast) hover:bg-surface-container disabled:opacity-50"
            >
              Create separately: {parts.join(", ")}
            </button>
          ) : null}
          {!exact ? (
            <button
              type="button"
              disabled={creating}
              onClick={() => void create([query.trim()])}
              className="block min-h-11 w-full rounded-field px-4 py-2 text-left text-body font-medium text-accent-active transition-colors duration-(--duration-fast) hover:bg-surface-container disabled:opacity-50"
            >
              {parts.length > 1 ? `Keep exact label: ${query.trim()}` : `Create ${query.trim()}`}
            </button>
          ) : null}
        </div>
      ) : null}
      {createError ? <p className="mt-2 text-meta text-danger">{createError}</p> : null}
      {compact ? null : (
        <p className="mt-2 text-meta text-ink-a40">
          Categories help customers browse. Select only the ones that genuinely fit.
        </p>
      )}
    </fieldset>
  );
}
