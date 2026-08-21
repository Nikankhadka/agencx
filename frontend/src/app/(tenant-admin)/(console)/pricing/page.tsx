"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiFetch, ApiError } from "@/lib/api";
import { useApiQuery, errorMessage } from "@/lib/useApiQuery";
import { formatCents } from "@/lib/money";

interface PricingRule {
  id: string;
  code: string;
  label: string;
  unit_amount_cents: number;
  unit: string;
  active: boolean;
  updated_at: string;
}

interface CatalogItem {
  id: string;
  name: string;
  description: string;
  price_cents: number | null;
  active: boolean;
  updated_at: string;
}

interface RuleDraft {
  code: string;
  label: string;
  amount: string;
  unit: string;
  active: boolean;
}

/**
 * One-off display transform: integer cents -> the plain "120.00" string an
 * <input type="number"> needs (no currency symbol). This is not shared money
 * formatting - formatCents renders "$120.00", wrong for an editable field - so
 * it lives here rather than in src/lib/money.ts.
 */
function centsToAmountInput(cents: number): string {
  return (cents / 100).toFixed(2);
}

const INPUT_CLASS =
  "w-full rounded-md border border-border bg-surface px-2 py-1 text-body-sm text-text transition-colors duration-(--duration-fast) hover:border-border-strong";

/**
 * T-031 / T-060: Pricing tab (frontend.md 7.2), rebuilt as a card list rather
 * than a table. Each pricing rule is a card with the code, label, amount +
 * unit, active state, and an inline editor; catalog items are simpler cards.
 * The client sends decimal dollars; the backend does the cents conversion
 * (deterministic-pricing rule). Validation errors from the PATCH render
 * inline, never as an alert.
 */
export default function PricingPage() {
  const rulesQuery = useApiQuery<PricingRule[]>("/api/pricing/rules");
  const catalogQuery = useApiQuery<CatalogItem[]>("/api/pricing/catalog");
  const rules = rulesQuery.data ?? [];
  const catalog = catalogQuery.data ?? [];

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<RuleDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  function startEdit(rule: PricingRule) {
    setEditingId(rule.id);
    setEditError(null);
    setDraft({
      code: rule.code,
      label: rule.label,
      amount: centsToAmountInput(rule.unit_amount_cents),
      unit: rule.unit,
      active: rule.active,
    });
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft(null);
    setEditError(null);
  }

  async function saveEdit(id: string) {
    if (!draft) return;
    setSaving(true);
    setEditError(null);
    try {
      await apiFetch(`/api/pricing/rules/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          code: draft.code,
          label: draft.label,
          unit_amount_dollars: draft.amount,
          unit: draft.unit,
          active: draft.active,
        }),
      });
      cancelEdit();
      await rulesQuery.refetch();
    } catch (err) {
      // 422 (validation) / 409 (duplicate code) render inline per frontend.md.
      setEditError(err instanceof ApiError ? err.detail : "Failed to save changes");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 p-8">
      <div>
        <h1 className="text-title-2 font-semibold text-text">Pricing</h1>
        <p className="mt-1 text-body-sm text-text-secondary">
          The rules and catalog your assistant quotes from.
        </p>
      </div>

      <div
        role="note"
        className="rounded-md border border-border bg-info-subtle px-4 py-2 text-body-sm text-info"
      >
        Changes apply to new quotes only.
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-title-3 font-semibold text-text">Pricing rules</h2>
        {rulesQuery.isPending ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 2 }).map((_, index) => (
              <div
                key={index}
                className="h-20 animate-pulse rounded-card border border-border bg-surface"
              />
            ))}
          </div>
        ) : errorMessage(rulesQuery.error, "Failed to load pricing rules") ? (
          <p className="text-body-sm text-danger">
            {errorMessage(rulesQuery.error, "Failed to load pricing rules")}
          </p>
        ) : rules.length === 0 ? (
          <EmptyState
            title="No pricing rules yet"
            description="Pricing rules are captured during onboarding and power deterministic quotes."
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {rules.map((rule) => {
              const editing = editingId === rule.id && draft !== null;
              return (
                <li
                  key={rule.id}
                  className="rounded-card border border-border bg-surface p-4 shadow-card"
                >
                  {editing && draft ? (
                    <div className="flex flex-col gap-3">
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <label className="flex flex-col gap-1">
                          <span className="text-footnote text-text-secondary">Code</span>
                          <input
                            aria-label="Code"
                            className={INPUT_CLASS}
                            value={draft.code}
                            onChange={(e) => setDraft({ ...draft, code: e.target.value })}
                          />
                        </label>
                        <label className="flex flex-col gap-1">
                          <span className="text-footnote text-text-secondary">Label</span>
                          <input
                            aria-label="Label"
                            className={INPUT_CLASS}
                            value={draft.label}
                            onChange={(e) => setDraft({ ...draft, label: e.target.value })}
                          />
                        </label>
                        <label className="flex flex-col gap-1">
                          <span className="text-footnote text-text-secondary">Amount in dollars</span>
                          <input
                            aria-label="Amount in dollars"
                            type="number"
                            step="0.01"
                            min="0"
                            className={`${INPUT_CLASS} tabular-nums`}
                            value={draft.amount}
                            onChange={(e) => setDraft({ ...draft, amount: e.target.value })}
                          />
                        </label>
                        <label className="flex flex-col gap-1">
                          <span className="text-footnote text-text-secondary">Unit</span>
                          <input
                            aria-label="Unit"
                            className={INPUT_CLASS}
                            value={draft.unit}
                            onChange={(e) => setDraft({ ...draft, unit: e.target.value })}
                          />
                        </label>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <label className="flex items-center gap-2 text-body-sm text-text">
                          <input
                            type="checkbox"
                            className="accent-accent"
                            checked={draft.active}
                            onChange={(e) => setDraft({ ...draft, active: e.target.checked })}
                          />
                          Active
                        </label>
                        <div className="flex items-center gap-2">
                          <Button size="sm" loading={saving} onClick={() => saveEdit(rule.id)}>
                            Save
                          </Button>
                          <Button size="sm" variant="ghost" onClick={cancelEdit}>
                            Cancel
                          </Button>
                        </div>
                      </div>
                      {editError ? <p className="text-footnote text-danger">{editError}</p> : null}
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-caption text-text-secondary">
                            {rule.code}
                          </span>
                          <Badge tone={rule.active ? "success" : "neutral"}>
                            {rule.active ? "active" : "inactive"}
                          </Badge>
                        </div>
                        <p className="mt-1 text-row-title font-medium text-text">{rule.label}</p>
                        <p className="mt-0.5 text-body text-text">
                          <span className="tabular-nums">{formatCents(rule.unit_amount_cents)}</span>{" "}
                          <span className="text-text-tertiary">/ {rule.unit}</span>
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={editingId !== null}
                        onClick={() => startEdit(rule)}
                      >
                        Edit
                      </Button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-title-3 font-semibold text-text">Catalog items</h2>
        {catalogQuery.isPending ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 2 }).map((_, index) => (
              <div
                key={index}
                className="h-16 animate-pulse rounded-card border border-border bg-surface"
              />
            ))}
          </div>
        ) : errorMessage(catalogQuery.error, "Failed to load catalog") ? (
          <p className="text-body-sm text-danger">
            {errorMessage(catalogQuery.error, "Failed to load catalog")}
          </p>
        ) : catalog.length === 0 ? (
          <EmptyState
            title="No catalog items yet"
            description="Products and services you offer will appear here once added."
          />
        ) : (
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {catalog.map((item) => (
              <li
                key={item.id}
                className="rounded-card border border-border bg-surface p-4 shadow-card"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-row-title font-medium text-text">{item.name}</p>
                  <Badge tone={item.active ? "success" : "neutral"}>
                    {item.active ? "active" : "inactive"}
                  </Badge>
                </div>
                {item.description ? (
                  <p className="mt-1 text-body-sm text-text-secondary">{item.description}</p>
                ) : null}
                <p className="mt-2 text-body tabular-nums text-text">
                  {item.price_cents === null ? "-" : formatCents(item.price_cents)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
