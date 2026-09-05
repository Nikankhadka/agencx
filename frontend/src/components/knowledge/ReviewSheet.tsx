"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import type {
  KnowledgeRecord,
  KnowledgeSection,
  PendingOffering,
  ReviewOffering,
} from "./types";
import { sourceLabel } from "./types";

interface WorkingOffering extends PendingOffering {
  priceText: string;
  priceOptions: number[];
  /** W-6: the source's own wording for a price that could not be reduced to one
   *  flat amount, shown instead of a number picked out of it. */
  priceNote: string;
  /** W-6: names the extraction thinks might be this same item. Never merged
   *  automatically - W-8 turns these into a combine/keep-both choice. */
  possibleMatches: string[];
}

/**
 * One server candidate as the editor holds it.
 *
 * W-6 put three new decisions on the wire, and this is where they turn into
 * what the owner sees. The one that carries product meaning is `priceNote`: it
 * is populated only when the server flagged the row, because the note is the
 * source's own wording for a price it refused to reduce to a number ("$20-$30",
 * "mostly $10-14"). An unflagged row has no note to show even if the column
 * carries text, and an absent price is not a flag - a source is allowed to be
 * silent about what something costs.
 */
export function toWorkingOffering(item: ReviewOffering): WorkingOffering {
  return {
    name: item.name,
    description: item.description ?? "",
    price_cents: item.price_cents,
    sources: item.sources,
    priceText: item.price_cents == null ? "" : formatPrice(item.price_cents),
    priceOptions: item.price_options ?? [],
    priceNote: item.needs_review ? (item.price_note ?? "") : "",
    possibleMatches: item.possible_matches ?? [],
  };
}

export interface ReviewSheetProps {
  record: KnowledgeRecord | null;
  busy: boolean;
  priceConflict: string | null;
  onboarding?: boolean;
  onClose: () => void;
  onSave: (
    sections: KnowledgeSection[],
    offerings: PendingOffering[],
    acceptPriceChanges?: boolean,
  ) => void;
  onDiscard: () => void;
}

export function ReviewSheet({
  record,
  busy,
  priceConflict,
  onboarding = false,
  onClose,
  onSave,
  onDiscard,
}: ReviewSheetProps) {
  return (
    <Sheet
      open={record !== null}
      onClose={onClose}
      title={onboarding ? "Review your information" : record?.status === "draft" ? "Read this back" : "Edit what I know"}
    >
      {record ? (
        <SectionEditor
          key={record.id}
          record={record}
          busy={busy}
          priceConflict={priceConflict}
          onboarding={onboarding}
          onSave={onSave}
          onDiscard={onDiscard}
        />
      ) : null}
    </Sheet>
  );
}

function SectionEditor({
  record,
  busy,
  priceConflict,
  onboarding,
  onSave,
  onDiscard,
}: Omit<ReviewSheetProps, "record" | "onClose"> & { record: KnowledgeRecord; onboarding: boolean }) {
  const [sections, setSections] = useState<KnowledgeSection[]>(() =>
    record.sections.map((section) => ({ ...section })),
  );
  const [offerings, setOfferings] = useState<WorkingOffering[]>(() =>
    (record.offering_candidates ?? []).map(toWorkingOffering),
  );

  const duplicate = hasDuplicateNames(offerings);
  const unresolved = offerings.some((item) => item.priceOptions.length > 1);

  function updateOffering(index: number, update: Partial<WorkingOffering>) {
    setOfferings((previous) => previous.map((item, position) => position === index ? { ...item, ...update } : item));
  }

  function save() {
    if (duplicate || unresolved) return;
    onSave(
      sections,
      offerings
        .map((item) => ({
          name: item.name.trim(),
          description: item.description,
          sources: item.sources,
          price_cents: parsePriceCents(item.priceText),
        }))
        .filter((item) => item.name),
      priceConflict !== null,
    );
  }

  return (
    <div className="flex max-h-[calc(100dvh-7rem)] flex-col gap-[18px] overflow-y-auto pb-2">
      <p className="text-meta text-ink-a40">
        {onboarding
          ? `Here's what I got from ${sourceLabel(record)}. Fix anything that's wrong before you use it.`
          : record.status === "draft"
            ? `Here's what I got from ${sourceLabel(record)}. Fix anything that's wrong - it only starts answering customers once you save it.`
            : `From ${sourceLabel(record)}. Your assistant answers from exactly this text.`}
      </p>

      {sections.length === 0 ? (
        <p className="text-prose text-text">I couldn&apos;t read anything usable from this one.</p>
      ) : null}
      {/* W-7: the offering headings are shown as priced cards below, not as raw
          text - the owner read the same menu three times otherwise. The sections
          stay in state and still round-trip on save, so the text the assistant
          answers from is unchanged; only their editors are hidden here. */}
      {sections.map((section, index) =>
        OFFERING_HEADINGS.has(section.heading) ? null : (
          <SectionField
            key={`${section.heading}-${index}`}
            heading={section.heading}
            body={section.body}
            onChange={(body) => setSections((previous) => previous.map((item, position) => position === index ? { ...item, body } : item))}
          />
        ),
      )}

      <fieldset className="rounded-card border border-hairline p-4">
        <legend className="px-1 text-row-label font-medium text-text">What you offer</legend>
        <p className="mb-3 text-meta text-ink-a40">Check the names, descriptions, and prices before saving.</p>
        {/* W-6 US-2: a partly-read document must say so. A truncated list that
            looks complete is worse than a short one that admits it. */}
        {record.extraction_status === "partial" || record.extraction_status === "failed" ? (
          <p role="status" className="mb-3 rounded-field bg-warning-subtle p-2 text-meta text-text">
            {record.extraction_status === "failed"
              ? "I could not read the offerings out of this one."
              : "I could not read all of this document."}{" "}
            Add anything missing here, or check the sections above against your original.
          </p>
        ) : null}
        <div className="flex flex-col gap-3">
          {offerings.map((offering, index) => (
            <div key={index} className="rounded-field bg-surface-container p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="rounded-full bg-accent-a12 px-2 py-1 text-meta text-accent">
                  {sourceText(offering.sources)}
                </span>
                <button
                  type="button"
                  aria-label={`Remove offering ${index + 1}`}
                  onClick={() => setOfferings((previous) => previous.filter((_, position) => position !== index))}
                  className="text-action text-ink-a40 active:opacity-60"
                >
                  Remove
                </button>
              </div>
              {/* W-7: name and price sit on one row - the offering and what it
                  costs read together - with the description beneath, so an owner
                  manages one compact card per item instead of three lists. */}
              <div className="flex gap-2">
                <label className="block grow">
                  <span className="sr-only">Offering {index + 1} name</span>
                  <input
                    value={offering.name}
                    aria-label={`Offering ${index + 1} name`}
                    placeholder="Offering"
                    onChange={(event) => updateOffering(index, { name: event.target.value })}
                    className="w-full rounded-field border-[length:var(--border-chip)] border-transparent bg-surface px-3 py-2 text-field text-text outline-none focus:border-accent-a35"
                  />
                </label>
                <label className="block w-24 shrink-0">
                  <span className="sr-only">Offering {index + 1} price</span>
                  <input
                    value={offering.priceText}
                    aria-label={`Offering ${index + 1} price`}
                    placeholder="Price"
                    inputMode="decimal"
                    onChange={(event) => updateOffering(index, { priceText: event.target.value, priceOptions: [] })}
                    className="w-full rounded-field border-[length:var(--border-chip)] border-transparent bg-surface px-3 py-2 text-field text-text outline-none focus:border-accent-a35"
                  />
                </label>
              </div>
              <label className="mt-2 block">
                <span className="sr-only">Offering {index + 1} description</span>
                <input
                  value={offering.description}
                  aria-label={`Offering ${index + 1} description`}
                  placeholder="Description (optional)"
                  onChange={(event) => updateOffering(index, { description: event.target.value })}
                  className="w-full rounded-field border-[length:var(--border-chip)] border-transparent bg-surface px-3 py-2 text-field text-text outline-none focus:border-accent-a35"
                />
              </label>
              {/* W-6: a price the row cannot hold - a range, a "from" price, a
                  rate. The source's own wording is shown rather than a number
                  picked out of it, so the owner types the one that is right. */}
              {offering.priceNote ? (
                <p className="mt-2 rounded-field bg-warning-subtle p-2 text-meta text-text">
                  <span className="font-medium">Check this price.</span> The source says:{" "}
                  {offering.priceNote}
                </p>
              ) : null}
              {/* W-6: similar names stay separate rows. Merging on similarity
                  would silently delete a real offering, so this is a pointer,
                  not a decision - W-8 makes it one. */}
              {offering.possibleMatches.length > 0 ? (
                <p className="mt-2 text-meta text-ink-a40">
                  Might be the same as {offering.possibleMatches.join(", ")}. Both are kept unless
                  you remove one.
                </p>
              ) : null}
              {offering.priceOptions.length > 1 ? (
                <div role="alert" className="mt-2 rounded-field bg-accent-a06 p-2 text-meta text-text">
                  This source has two prices. Choose one or type the final price.
                  <div className="mt-2 flex flex-wrap gap-2">
                    {offering.priceOptions.map((price) => (
                      <button
                        key={price}
                        type="button"
                        onClick={() => updateOffering(index, { price_cents: price, priceText: formatPrice(price), priceOptions: [] })}
                        className="rounded-full border border-accent-a35 px-3 py-1 text-action text-accent"
                      >
                        Use {formatPrice(price)}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setOfferings((previous) => [...previous, { name: "", description: "", price_cents: null, sources: ["owner"], priceText: "", priceOptions: [], priceNote: "", possibleMatches: [] }])}
          className="mt-3 text-action font-medium text-accent active:opacity-60"
        >
          Add another offering
        </button>
        {duplicate ? <p role="alert" className="mt-2 text-meta text-danger">Offering names must be unique.</p> : null}
      </fieldset>

      {priceConflict ? <p role="alert" className="rounded-card bg-accent-a06 p-3 text-meta text-text">{priceConflict}</p> : null}
      <div className="flex flex-col gap-2.5">
        <Button
          className="w-full rounded-field py-4"
          loading={busy}
          disabled={sections.length === 0 || duplicate || unresolved}
          onClick={save}
          data-testid={onboarding ? "onboarding-knowledge-save" : "knowledge-save"}
        >
          {onboarding ? "Use this information" : priceConflict ? "Confirm price changes" : record.status === "draft" ? "Save it" : "Save changes"}
        </Button>
        <button type="button" onClick={onDiscard} disabled={busy} className="py-2 text-action font-medium text-ink-a40 active:opacity-60" data-testid={onboarding ? "onboarding-knowledge-discard" : "knowledge-discard"}>
          {onboarding || record.status === "draft" ? "Discard this" : "Remove this"}
        </button>
      </div>
    </div>
  );
}

function SectionField({ heading, body, onChange }: { heading: string; body: string; onChange: (body: string) => void }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    if (!ref.current) return;
    ref.current.style.height = "auto";
    ref.current.style.height = `${ref.current.scrollHeight}px`;
  }, [body]);
  return (
    <label className="block">
      <span className="mb-2 block text-field-label font-medium uppercase text-ink-a40">{heading}</span>
      <textarea ref={ref} value={body} rows={1} onChange={(event) => onChange(event.target.value)} className="w-full resize-none overflow-hidden rounded-field border-[length:var(--border-chip)] border-transparent bg-surface-container px-[18px] py-3.5 text-field text-text outline-none transition-colors duration-(--duration-fast) focus:border-accent-a35 focus:bg-accent-a06" />
    </label>
  );
}

// W-7: mirrors OFFERING_HEADINGS in
// backend/app/features/business/offering_candidates.py - the two structured
// headings whose lines become priced offering cards, so their raw text is not
// also shown as an editable section.
const OFFERING_HEADINGS = new Set(["What we offer", "Prices"]);


function hasDuplicateNames(offerings: WorkingOffering[]): boolean {
  const names = offerings.map((item) => normalizeName(item.name)).filter(Boolean);
  return new Set(names).size !== names.length;
}

function normalizeName(value: string): string {
  return value.normalize("NFKC").trim().toLowerCase().replace(/[\p{P}]/gu, " ").replace(/\s+/g, " ");
}

function sourceText(sources: PendingOffering["sources"]): string {
  return sources.includes("owner") && sources.includes("document") ? "Both" : sources.includes("owner") ? "You entered" : "From document";
}

function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function parsePriceCents(value: string): number | null {
  const normalized = value.trim().replace(/[ $,]/g, "");
  if (!normalized || !/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const [dollars, cents = ""] = normalized.split(".");
  return Number(dollars) * 100 + Number(`${cents}00`.slice(0, 2));
}
