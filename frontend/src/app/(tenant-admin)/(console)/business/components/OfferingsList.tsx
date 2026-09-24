"use client";

import { useEffect, useState } from "react";
import { toast } from "react-hot-toast";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { OfferingMediaField } from "./OfferingMediaField";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { ApiError, apiFetch } from "@/lib/api";
import { CategoryPicker, type CategoryOption } from "@/components/business/CategoryPicker";

interface Offering {
  id: string;
  name: string;
  description: string;
  price_cents: number | null;
  category?: string | null;
  category_id?: string | null;
  categories: Array<{ id: string; name: string; position: number; is_primary: boolean }>;
  media?: { url: string } | null;
}

interface OfferingCategory extends CategoryOption {
  normalized_key: string;
  offering_count: number;
}

interface OfferingGroup {
  label: string;
  offerings: Offering[];
}

function groupOfferings(offerings: Offering[]): OfferingGroup[] {
  const groups = new Map<string, Offering[]>();
  for (const offering of offerings) {
    const label = offering.category?.trim() || UNCATEGORIZED;
    groups.set(label, [...(groups.get(label) ?? []), offering]);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => {
      if (left === UNCATEGORIZED) return 1;
      if (right === UNCATEGORIZED) return -1;
      return left.localeCompare(right);
    })
    .map(([label, items]) => ({
      label,
      offerings: items.sort((left, right) => left.name.localeCompare(right.name)),
    }));
}

const UNCATEGORIZED = "Uncategorized";

interface FormValues {
  name: string;
  description: string;
  price: string;
  categoryIds: string[];
  primaryCategoryId: string | null;
  mediaUrl: string;
  mediaFile: File | null;
  mediaChanged: boolean;
  removeMedia: boolean;
}

const EMPTY_FORM: FormValues = {
  name: "",
  description: "",
  price: "",
  categoryIds: [],
  primaryCategoryId: null,
  mediaUrl: "",
  mediaFile: null,
  mediaChanged: false,
  removeMedia: false,
};

function formFor(offering: Offering): FormValues {
  return {
    name: offering.name,
    description: offering.description,
    price:
      offering.price_cents === null
        ? ""
        : (offering.price_cents / 100).toFixed(2),
    categoryIds: offering.categories.map((category) => category.id),
    primaryCategoryId: offering.category_id ?? null,
    mediaUrl: offering.media?.url ?? "",
    mediaFile: null,
    mediaChanged: false,
    removeMedia: false,
  };
}

export function OfferingsList() {
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [categories, setCategories] = useState<OfferingCategory[]>([]);
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [categoryEditing, setCategoryEditing] = useState<string | "new" | null>(null);
  const [categoryDraft, setCategoryDraft] = useState("");
  const [form, setForm] = useState<FormValues>(EMPTY_FORM);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [working, setWorking] = useState(false);
  // Loading the list is the one failure that stays inline - every mutation
  // reports through a toast instead, so a failure never hides inside a form
  // the owner already closed.
  const [loadError, setLoadError] = useState<string | null>(null);
  const { confirm, dialog: confirmDialog } = useConfirm();
  const groups = groupOfferings(offerings);

  async function load() {
    try {
      const [nextOfferings, nextCategories] = await Promise.all([
        apiFetch<Offering[]>("/api/business/offerings"),
        apiFetch<OfferingCategory[]>("/api/business/offering-categories"),
      ]);
      setOfferings(nextOfferings);
      setCategories(nextCategories);
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.detail : "Couldn't load what you offer.");
    }
  }

  // Deliberately not `void load()`: react-hooks/set-state-in-effect cannot see
  // that the setState inside an async function is deferred past an await, and
  // rejects it. Written as a visible callback, the rule is satisfied and the
  // behaviour is identical. `load()` stays for the mutation handlers below.
  useEffect(() => {
    Promise.all([
      apiFetch<Offering[]>("/api/business/offerings"),
      apiFetch<OfferingCategory[]>("/api/business/offering-categories"),
    ])
      .then(([rows, nextCategories]) => {
        setOfferings(rows);
        setCategories(nextCategories);
        setLoadError(null);
      })
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.detail : "Couldn't load what you offer."),
      );
  }, []);

  function begin(offering?: Offering) {
    setEditing(offering?.id ?? "new");
    setForm(offering ? formFor(offering) : EMPTY_FORM);
    setDetailsOpen(
      Boolean(
        offering &&
          (offering.category ||
            offering.description ||
            offering.price_cents !== null ||
            offering.media),
      ),
    );
  }

  function close() {
    if (!working) setEditing(null);
  }

  function beginCategory(category?: OfferingCategory) {
    setCategoryEditing(category?.id ?? "new");
    setCategoryDraft(category?.name ?? "");
  }

  function closeCategory() {
    if (!working) setCategoryEditing(null);
  }

  async function saveCategory() {
    const name = categoryDraft.trim();
    if (!name || !categoryEditing || working) return;
    const isNew = categoryEditing === "new";
    setWorking(true);
    try {
      if (isNew) {
        await createCategory(name);
      } else {
        await apiFetch(`/api/business/offering-categories/${categoryEditing}`, {
          method: "PATCH",
          body: JSON.stringify({ name }),
        });
        await load();
      }
      setCategoryEditing(null);
      toast.success(isNew ? "Category added" : "Category renamed");
    } catch (err) {
      toast.error(
        err instanceof ApiError
          ? err.detail
          : isNew
            ? "Couldn't add that category."
            : "Couldn't rename that category.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function createCategory(name: string): Promise<OfferingCategory> {
    const created = await apiFetch<OfferingCategory>("/api/business/offering-categories", {
      method: "POST",
      body: JSON.stringify({ name: name.trim() }),
    });
    setCategories((current) =>
      [...current.filter((category) => category.id !== created.id), created].sort((left, right) =>
        left.name.localeCompare(right.name),
      ),
    );
    return created;
  }

  async function removeCategory(category: OfferingCategory) {
    if (working) return;
    await confirm({
      title: `Remove ${category.name}?`,
      description: "It will be removed from its offerings. Another selected category becomes primary.",
      confirmLabel: "Remove category",
      tone: "danger",
      onConfirm: async () => {
        setWorking(true);
        try {
          await apiFetch(`/api/business/offering-categories/${category.id}`, { method: "DELETE" });
          await load();
          toast.success("Category removed");
        } catch (err) {
          toast.error(err instanceof ApiError ? err.detail : "Couldn't remove that category.");
        } finally {
          setWorking(false);
        }
      },
    });
  }

  async function save() {
    if (!editing || !form.name.trim()) return;
    const isNew = editing === "new";
    setWorking(true);
    const body = {
      name: form.name,
      description: form.description,
      price_dollars: form.price.trim() || null,
      category_ids: form.categoryIds,
      primary_category_id: form.primaryCategoryId,
    };
    try {
      const path = editing === "new" ? "/api/business/offerings" : `/api/business/offerings/${editing}`;
      const saved = await apiFetch<Offering>(path, {
        method: editing === "new" ? "POST" : "PATCH",
        body: JSON.stringify(body),
      });
      if (form.removeMedia) {
        await apiFetch(`/api/business/offerings/${saved.id}/media`, {
          method: "DELETE",
        });
      } else if (form.mediaChanged && form.mediaUrl.trim()) {
        await apiFetch(`/api/business/offerings/${saved.id}/media/url`, {
          method: "PUT",
          body: JSON.stringify({ url: form.mediaUrl.trim() }),
        });
      } else if (form.mediaChanged && form.mediaFile) {
        const media = new FormData();
        media.append("file", form.mediaFile);
        await apiFetch(`/api/business/offerings/${saved.id}/media/upload`, {
          method: "PUT",
          body: media,
        });
      }
      setEditing(null);
      await load();
      toast.success(isNew ? "Offering added" : "Offering saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Couldn't save that offering.");
    } finally {
      setWorking(false);
    }
  }

  async function remove(offering: Offering) {
    if (working) return;
    await confirm({
      title: `Remove ${offering.name}?`,
      description: "Customers will no longer see it on your page.",
      confirmLabel: "Remove",
      tone: "danger",
      onConfirm: async () => {
        setWorking(true);
        try {
          await apiFetch(`/api/business/offerings/${offering.id}`, { method: "DELETE" });
          await load();
          toast.success("Offering removed");
        } catch (err) {
          toast.error(err instanceof ApiError ? err.detail : "Couldn't remove that offering.");
        } finally {
          setWorking(false);
        }
      },
    });
  }

  async function confirmRemoveMedia() {
    await confirm({
      title: "Remove this photo?",
      description: "The offering stays - only its photo goes.",
      confirmLabel: "Remove",
      tone: "danger",
      onConfirm: () => {
        setForm((current) => ({ ...current, mediaChanged: true, removeMedia: true }));
      },
    });
  }

  return (
    <>
    <section className="border-b border-hairline px-gutter py-5" aria-labelledby="categories-heading">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="categories-heading" className="text-row-label font-medium text-text">
            Categories
          </h2>
          <p className="mt-1 text-meta text-ink-a40">
            Organize how customers browse what you offer.
          </p>
        </div>
        {categoryEditing === null ? (
          <button
            type="button"
            onClick={() => beginCategory()}
            data-testid="category-add"
            className="flex shrink-0 items-center gap-1 text-action font-medium text-accent-active transition-colors duration-(--duration-fast) hover:underline active:opacity-60"
          >
            <Icon name="add" size={16} />
            Add
          </button>
        ) : null}
      </div>
      {categories.length ? (
        <ul className="mt-3 divide-y divide-hairline" data-testid="categories-list">
          {categories.map((category) => (
            <li key={category.id} className="flex items-center gap-3 py-3">
              <span className="min-w-0 flex-1">
                <span className="block text-card-hl font-medium text-text">{category.name}</span>
                <span className="mt-1 block text-meta text-ink-a40">
                  {category.offering_count} active {category.offering_count === 1 ? "offering" : "offerings"}
                </span>
              </span>
              <button
                type="button"
                onClick={() => beginCategory(category)}
                disabled={working}
                aria-label={`Edit ${category.name}`}
                className="flex size-icon-btn shrink-0 items-center justify-center rounded-full text-ink-a40 transition-colors duration-(--duration-fast) hover:bg-surface-container hover:text-text active:bg-surface-container-high disabled:opacity-50"
              >
                <Icon name="edit" size={18} />
              </button>
              <button
                type="button"
                onClick={() => void removeCategory(category)}
                disabled={working}
                aria-label={`Remove ${category.name}`}
                className="flex size-icon-btn shrink-0 items-center justify-center rounded-full text-ink-a40 transition-colors duration-(--duration-fast) hover:bg-surface-container hover:text-text active:bg-surface-container-high disabled:opacity-50"
              >
                <Icon name="delete" size={18} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-prose text-ink-a40">No categories yet.</p>
      )}
      <Modal
        open={categoryEditing !== null}
        onClose={closeCategory}
        title={categoryEditing === "new" ? "New category" : "Edit category"}
      >
        {categoryEditing !== null ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void saveCategory();
            }}
          >
            <input
              autoFocus
              required
              value={categoryDraft}
              onChange={(event) => setCategoryDraft(event.target.value)}
              placeholder="Category name"
              aria-label="Category name"
              data-testid="category-name"
              className="w-full rounded-field border border-border bg-surface px-3 py-2 text-field text-text outline-none placeholder:text-ink-a40 focus:border-text"
            />
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="submit"
                loading={working}
                disabled={!categoryDraft.trim()}
                data-testid="category-save"
              >
                Save
              </Button>
              <Button type="button" variant="secondary" onClick={closeCategory} disabled={working}>
                Cancel
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>
    </section>
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
            className="flex shrink-0 items-center gap-1 text-action font-medium text-accent-active transition-colors duration-(--duration-fast) hover:underline active:opacity-60"
          >
            <Icon name="add" size={16} />
            Add
          </button>
        ) : null}
      </div>

      {offerings.length > 0 ? (
        <div className="mt-3" data-testid="offerings-list">
          {groups.map((group) => (
              <section key={group.label} className="mb-5 last:mb-0" aria-labelledby={`offerings-${group.label}`}>
                <h3 id={`offerings-${group.label}`} className="text-label font-medium uppercase text-ink-a40">
                  {group.label}
                </h3>
                <ul className="mt-1 divide-y divide-hairline">
                  {group.offerings.map((offering) => (
                    <li key={offering.id} className="flex items-center gap-3 py-3">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-card-hl font-medium text-text">{offering.name}</span>
                        {offering.description ? (
                          <span className="mt-1 block truncate text-meta text-ink-a40">
                            {offering.description}
                          </span>
                        ) : null}
                        {offering.price_cents !== null ? (
                          <span className="mt-1 block text-meta text-ink-a40">
                            ${(offering.price_cents / 100).toFixed(2)}
                          </span>
                        ) : null}
                        {offering.categories.some((category) => !category.is_primary) ? (
                          <span className="mt-1 flex flex-wrap gap-1">
                            {offering.categories
                              .filter((category) => !category.is_primary)
                              .map((category) => (
                                <span key={category.id} className="rounded-full bg-surface-container px-2 py-1 text-meta text-ink-a40">
                                  {category.name}
                                </span>
                              ))}
                          </span>
                        ) : null}
                      </span>
                      <button
                        type="button"
                        onClick={() => begin(offering)}
                        disabled={working}
                        aria-label={`Edit ${offering.name}`}
                        data-testid="offering-edit"
                        className="flex size-icon-btn shrink-0 items-center justify-center rounded-full text-ink-a40 transition-colors duration-(--duration-fast) hover:bg-surface-container hover:text-text active:bg-surface-container-high disabled:opacity-50"
                      >
                        <Icon name="edit" size={18} />
                      </button>
                      <button
                        type="button"
                        onClick={() => void remove(offering)}
                        disabled={working}
                        aria-label={`Remove ${offering.name}`}
                        data-testid="offering-remove"
                        className="flex size-icon-btn shrink-0 items-center justify-center rounded-full text-ink-a40 transition-colors duration-(--duration-fast) hover:bg-surface-container hover:text-text active:bg-surface-container-high disabled:opacity-50"
                      >
                        <Icon name="delete" size={18} />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
          ))}
        </div>
      ) : editing === null ? (
        <p className="mt-3 text-prose text-ink-a40">Nothing added yet.</p>
      ) : null}

      <Modal
        open={editing !== null}
        onClose={close}
        title={editing === "new" ? "New offering" : "Edit offering"}
      >
        {editing !== null ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <div className="flex gap-2">
            <input
              autoFocus
              required
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Offering"
              aria-label="Offering name"
              data-testid="offering-name"
              className="min-w-0 flex-1 rounded-field border border-border bg-surface px-3 py-2 text-field text-text outline-none placeholder:text-ink-a40 focus:border-text"
            />
            <input
              value={form.price}
              onChange={(event) => setForm((current) => ({ ...current, price: event.target.value }))}
              inputMode="decimal"
              placeholder="Price"
              aria-label="Price"
              data-testid="offering-price"
              className="w-24 rounded-field border border-border bg-surface px-3 py-2 text-field text-text outline-none placeholder:text-ink-a40 focus:border-text"
            />
          </div>
          <textarea
            value={form.description}
            onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
            placeholder="Description (optional)"
            aria-label="Description"
            rows={2}
            data-testid="offering-description"
            className="mt-2 w-full resize-y rounded-field border border-border bg-surface px-3 py-2 text-field text-text outline-none placeholder:text-ink-a40 focus:border-text"
          />
          <details
            open={detailsOpen}
            onToggle={(event) => setDetailsOpen(event.currentTarget.open)}
            className="mt-2"
          >
            <summary className="cursor-pointer text-label font-medium uppercase text-ink-a40 transition-colors duration-(--duration-fast) hover:text-text active:opacity-60">
              Add details
            </summary>
            <div className="mt-3">
              <CategoryPicker
                categories={categories}
                selectedIds={form.categoryIds}
                primaryId={form.primaryCategoryId}
                onChange={(categoryIds, primaryCategoryId) =>
                  setForm((current) => ({ ...current, categoryIds, primaryCategoryId }))
                }
                onCreate={createCategory}
              />
            </div>
            <OfferingMediaField
              mediaUrl={form.mediaUrl}
              mediaFile={form.mediaFile}
              mediaChanged={form.mediaChanged}
              removeMedia={form.removeMedia}
              working={working}
              onPickFile={(file) =>
                setForm((current) => ({
                  ...current,
                  mediaFile: file,
                  mediaUrl: "",
                  mediaChanged: true,
                  removeMedia: false,
                }))
              }
              onUrlChange={(value) =>
                setForm((current) => ({
                  ...current,
                  mediaUrl: value,
                  mediaFile: null,
                  mediaChanged: true,
                  removeMedia: false,
                }))
              }
              onCancelPending={(restoreUrl, restoreChanged) =>
                setForm((current) => ({
                  ...current,
                  mediaFile: null,
                  mediaUrl: restoreUrl,
                  mediaChanged: restoreChanged,
                  removeMedia: false,
                }))
              }
              onRemoveSaved={() => void confirmRemoveMedia()}
            />
          </details>
          <div className="mt-4 flex justify-end gap-2">
            <Button
              type="submit"
              loading={working}
              disabled={!form.name.trim()}
              data-testid="offering-save"
            >
              Save
            </Button>
            <Button type="button" variant="secondary" onClick={close} disabled={working}>
              Cancel
            </Button>
          </div>
        </form>
        ) : null}
      </Modal>
      {loadError ? <p className="mt-3 text-meta text-danger">{loadError}</p> : null}
      {confirmDialog}
    </section>
    </>
  );
}
