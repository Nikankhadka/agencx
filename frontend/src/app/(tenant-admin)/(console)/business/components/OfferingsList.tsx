"use client";

import { useEffect, useState } from "react";
import { toast } from "react-hot-toast";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { OfferingMediaField } from "./OfferingMediaField";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { ApiError, apiFetch } from "@/lib/api";

interface Offering {
  id: string;
  name: string;
  description: string;
  price_cents: number | null;
  category?: string | null;
  media?: { url: string } | null;
}

interface OfferingCategory {
  id: string;
  name: string;
  normalized_key: string;
}

interface OfferingGroup {
  label: string;
  /** The category row behind the label, when one owns it. A legacy label that
   *  no category row matches still groups, it just cannot be renamed. */
  category: OfferingCategory | null;
  offerings: Offering[];
}

function groupOfferings(offerings: Offering[], categories: OfferingCategory[]): OfferingGroup[] {
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
      category: categories.find((category) => category.name === label) ?? null,
      offerings: items.sort((left, right) => left.name.localeCompare(right.name)),
    }));
}

const UNCATEGORIZED = "Uncategorized";

interface FormValues {
  name: string;
  description: string;
  price: string;
  category: string;
  mediaUrl: string;
  mediaFile: File | null;
  mediaChanged: boolean;
  removeMedia: boolean;
}

const EMPTY_FORM: FormValues = {
  name: "",
  description: "",
  price: "",
  category: "",
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
    category: offering.category ?? "",
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
  const [categoryEditing, setCategoryEditing] = useState<string | null>(null);
  const [categoryDraft, setCategoryDraft] = useState("");
  const [form, setForm] = useState<FormValues>(EMPTY_FORM);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [working, setWorking] = useState(false);
  // Loading the list is the one failure that stays inline - every mutation
  // reports through a toast instead, so a failure never hides inside a form
  // the owner already closed.
  const [loadError, setLoadError] = useState<string | null>(null);
  const { confirm, dialog: confirmDialog } = useConfirm();
  const groups = groupOfferings(offerings, categories);

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

  function beginCategory(category: OfferingCategory) {
    setCategoryEditing(category.id);
    setCategoryDraft(category.name);
  }

  async function saveCategory(category: OfferingCategory) {
    const name = categoryDraft.trim();
    if (!name || working) return;
    setWorking(true);
    try {
      await apiFetch(`/api/business/offering-categories/${category.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      setCategoryEditing(null);
      await load();
      toast.success("Category renamed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Couldn't rename that category.");
    } finally {
      setWorking(false);
    }
  }

  async function removeCategory(category: OfferingCategory) {
    if (working) return;
    await confirm({
      title: `Delete ${category.name}?`,
      description: "Its offerings will move to Uncategorized.",
      confirmLabel: "Delete category",
      tone: "danger",
      onConfirm: async () => {
        setWorking(true);
        try {
          await apiFetch(`/api/business/offering-categories/${category.id}`, { method: "DELETE" });
          await load();
          toast.success("Category deleted");
        } catch (err) {
          toast.error(err instanceof ApiError ? err.detail : "Couldn't delete that category.");
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
      category: form.category.trim() || null,
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
          {groups.map((group) => {
            const category = group.category;
            return (
              <section key={group.label} className="mb-5 last:mb-0" aria-labelledby={`offerings-${group.label}`}>
                <div className="flex items-center justify-between gap-3">
                  <h3 id={`offerings-${group.label}`} className="text-label font-medium uppercase text-ink-a40">
                    {group.label}
                  </h3>
                  {category ? (
                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => beginCategory(category)}
                        className="text-action text-accent-active transition-colors duration-(--duration-fast) hover:underline active:opacity-60"
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        onClick={() => void removeCategory(category)}
                        className="text-action text-ink-a40 transition-colors duration-(--duration-fast) hover:underline active:opacity-60"
                      >
                        Delete
                      </button>
                    </div>
                  ) : null}
                </div>
                {category && category.id === categoryEditing ? (
                  <div className="mt-2 flex gap-2">
                    <input
                      autoFocus
                      value={categoryDraft}
                      onChange={(event) => setCategoryDraft(event.target.value)}
                      aria-label={`Rename ${group.label}`}
                      className="min-w-0 flex-1 rounded-field border border-border bg-surface px-3 py-2 text-field text-text outline-none focus:border-text"
                    />
                    <Button size="sm" loading={working} onClick={() => void saveCategory(category)}>
                      Save
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setCategoryEditing(null)}>
                      Cancel
                    </Button>
                  </div>
                ) : null}
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
            );
          })}
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
            <label className="mt-3 block text-label font-medium uppercase text-ink-a40">
              Category <span className="normal-case">(optional)</span>
              <input data-testid="offering-category" value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))} className="mt-2 w-full rounded-field border border-border bg-surface px-3 py-2 text-field text-text outline-none focus:border-text" />
            </label>
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
  );
}
