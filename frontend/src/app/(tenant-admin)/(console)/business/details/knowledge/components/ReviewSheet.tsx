"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import type { KnowledgeRecord, KnowledgeSection } from "../lib/types";
import { sourceLabel } from "../lib/types";

export interface ReviewSheetProps {
  record: KnowledgeRecord | null;
  busy: boolean;
  priceConflict: string | null;
  onClose: () => void;
  onSave: (
    sections: KnowledgeSection[],
    offerings: { name: string; price_cents: number | null }[],
    acceptPriceChanges?: boolean,
  ) => void;
  onDiscard: () => void;
}

/**
 * Read back what we made of a source, and fix it before it answers anything.
 *
 * Every section is a plain textarea: the owner is correcting a text, not filling
 * a form, so there is nothing to validate and nothing to submit field by field.
 * The prototype's edit sheet (`#sheet-settings-edit`, `.se-label` / `.se-input` /
 * `.se-save-btn`) is the shape being followed.
 */
export function ReviewSheet({
  record,
  busy,
  priceConflict,
  onClose,
  onSave,
  onDiscard,
}: ReviewSheetProps) {
  return (
    <Sheet
      open={record !== null}
      onClose={onClose}
      title={record?.status === "draft" ? "Read this back" : "Edit what I know"}
    >
      {/* Keyed by record: opening a different source mounts a fresh editor, so
          the draft text never has to be synced back out of an effect. */}
      {record ? (
        <SectionEditor
          key={record.id}
          record={record}
          busy={busy}
          priceConflict={priceConflict}
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
  onSave,
  onDiscard,
}: {
  record: KnowledgeRecord;
  busy: boolean;
  priceConflict: string | null;
  onSave: (
    sections: KnowledgeSection[],
    offerings: { name: string; price_cents: number | null }[],
    acceptPriceChanges?: boolean,
  ) => void;
  onDiscard: () => void;
}) {
  const [sections, setSections] = useState<KnowledgeSection[]>(() =>
    record.sections.map((section) => ({ ...section })),
  );
  const [offerings, setOfferings] = useState(() =>
    (record.offering_candidates ?? []).map((offering) => ({ ...offering, selected: true })),
  );
  const draft = record.status === "draft";

  return (
    <div className="flex flex-col gap-[18px] pb-2">
      <p className="text-meta text-ink-a40">
        {draft
          ? `Here's what I got from ${sourceLabel(record)}. Fix anything that's wrong - it only starts answering customers once you save it.`
          : `From ${sourceLabel(record)}. Your assistant answers from exactly this text.`}
      </p>

      {sections.length === 0 ? (
        <p className="text-prose text-text">
          I couldn&apos;t read anything usable from this one. Remove it and try
          another file, or send me a link instead.
        </p>
      ) : null}

      {sections.map((section, index) => (
        <SectionField
          key={section.heading}
          heading={section.heading}
          body={section.body}
          onChange={(body) =>
            setSections((prev) =>
              prev.map((item, position) => (position === index ? { ...item, body } : item)),
            )
          }
        />
      ))}

      {offerings.length ? (
        <fieldset className="rounded-card border border-hairline p-4">
          <legend className="px-1 text-row-label font-medium text-text">Offerings found</legend>
          <p className="mb-3 text-meta text-ink-a40">Select the items to add, then check their names and prices.</p>
          {offerings.map((offering, index) => (
            <div key={`${offering.name}-${index}`} className="flex items-start gap-2 py-1.5 text-body-sm text-text">
              <input
                className="mt-2"
                type="checkbox"
                checked={offering.selected}
                onChange={() =>
                  setOfferings((prev) =>
                    prev.map((item, position) =>
                      position === index ? { ...item, selected: !item.selected } : item,
                    ),
                  )
                }
              />
              <div className="min-w-0 flex-1 space-y-1.5">
                <input
                  value={offering.name}
                  aria-label={`Offering ${index + 1} name`}
                  onChange={(event) =>
                    setOfferings((prev) =>
                      prev.map((item, position) =>
                        position === index ? { ...item, name: event.target.value } : item,
                      ),
                    )
                  }
                  className="w-full rounded-field border-[length:var(--border-chip)] border-transparent bg-surface-container px-3 py-2 text-field text-text outline-none focus:border-accent-a35"
                />
                <input
                  value={offering.price ?? ""}
                  aria-label={`Offering ${index + 1} price`}
                  placeholder="Price (optional)"
                  onChange={(event) =>
                    setOfferings((prev) =>
                      prev.map((item, position) =>
                        position === index ? { ...item, price: event.target.value } : item,
                      ),
                    )
                  }
                  className="w-full rounded-field border-[length:var(--border-chip)] border-transparent bg-surface-container px-3 py-2 text-field text-text outline-none focus:border-accent-a35"
                />
              </div>
            </div>
          ))}
        </fieldset>
      ) : null}

      {priceConflict ? (
        <p role="alert" className="rounded-card bg-accent-a06 p-3 text-meta text-text">
          {priceConflict} Confirm to update the existing offering prices.
        </p>
      ) : null}

      <div className="flex flex-col gap-2.5">
        <Button
          className="w-full rounded-field py-4"
          loading={busy}
          disabled={sections.length === 0}
          onClick={() =>
            onSave(
              sections,
              offerings
                .filter((item) => item.selected && item.name.trim())
                .map((item) => ({ name: item.name.trim(), price_cents: parsePriceCents(item.price) })),
              priceConflict !== null,
            )
          }
          data-testid="knowledge-save"
        >
          {priceConflict ? "Confirm price changes" : draft ? "Save it" : "Save changes"}
        </Button>
        <button
          type="button"
          onClick={onDiscard}
          disabled={busy}
          className="py-2 text-action font-medium text-ink-a40 active:opacity-60"
          data-testid="knowledge-discard"
        >
          {draft ? "Discard this" : "Remove this"}
        </button>
      </div>
    </div>
  );
}

function parsePriceCents(value: string | null): number | null {
  const normalized = (value ?? "").trim().replace(/[ $,]/g, "");
  if (!normalized || !/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const [dollars, cents = ""] = normalized.split(".");
  return Number(dollars) * 100 + Number(`${cents}00`.slice(0, 2));
}

/**
 * One section, in a box that grows to its text. A fixed height would hide the
 * end of a section behind an inner scrollbar, and a section the owner cannot
 * see whole is one they cannot check - which is the entire point of this sheet.
 */
function SectionField({
  heading,
  body,
  onChange,
}: {
  heading: string;
  body: string;
  onChange: (body: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${element.scrollHeight}px`;
  }, [body]);

  return (
    <label className="block">
      <span className="mb-2 block text-field-label font-medium uppercase text-ink-a40">
        {heading}
      </span>
      <textarea
        ref={ref}
        value={body}
        rows={1}
        onChange={(event) => onChange(event.target.value)}
        className="w-full resize-none overflow-hidden rounded-field border-[length:var(--border-chip)] border-transparent bg-surface-container px-[18px] py-3.5 text-field text-text outline-none transition-colors duration-(--duration-fast) focus:border-accent-a35 focus:bg-accent-a06"
      />
    </label>
  );
}
