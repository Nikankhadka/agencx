"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import type { ProfileUpdate } from "@/lib/api-schemas";

export interface ProfileFieldSheetProps {
  open: boolean;
  /** The API field this sheet writes; one editor per field kind, one save path. */
  field: keyof ProfileUpdate;
  title: string;
  label: string;
  value: string;
  placeholder?: string;
  /** Description is the one multi-line field; the rest are single-line. */
  multiline?: boolean;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (update: ProfileUpdate) => void;
}

/**
 * RF-2: one text field edited in the shipped ABN-sheet idiom. Business name,
 * hours, description and contact are all a labelled value with an explicit Save
 * and Cancel, so they share one sheet rather than four near-identical files.
 * The sheet-field recipe is `design/frontend.md` section 4.4; multi-line uses
 * the same recipe on a textarea.
 */
export function ProfileFieldSheet({
  open,
  field,
  title,
  label,
  value,
  placeholder,
  multiline = false,
  busy,
  error,
  onClose,
  onSave,
}: ProfileFieldSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} title={title}>
      {/* Keyed by what is saved, like the ABN sheet: reopening starts from the
          saved value, not from an abandoned edit. */}
      {open ? (
        <ProfileFieldEditor
          key={value}
          field={field}
          label={label}
          value={value}
          placeholder={placeholder}
          multiline={multiline}
          busy={busy}
          error={error}
          onClose={onClose}
          onSave={onSave}
        />
      ) : null}
    </Sheet>
  );
}

function ProfileFieldEditor({
  field,
  label,
  value,
  placeholder,
  multiline,
  busy,
  error,
  onClose,
  onSave,
}: Omit<ProfileFieldSheetProps, "open" | "title">) {
  const [draft, setDraft] = useState(value);
  const testId = String(field);
  const fieldClass =
    "w-full rounded-field border border-border bg-surface px-4 py-3 text-field text-text outline-none transition-colors duration-(--duration-fast) placeholder:text-ink-a40 focus:border-text disabled:opacity-50";

  return (
    <div className="flex flex-col gap-4 pb-2">
      <label className="block">
        <span className="mb-2 block text-label font-medium uppercase text-ink-a40">{label}</span>
        {multiline ? (
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={placeholder}
            rows={4}
            disabled={busy}
            autoFocus
            data-testid={`profile-${testId}-input`}
            className={`${fieldClass} resize-y`}
          />
        ) : (
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={placeholder}
            disabled={busy}
            autoFocus
            data-testid={`profile-${testId}-input`}
            className={fieldClass}
          />
        )}
      </label>

      {error ? (
        <p role="alert" className="text-meta text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex gap-2">
        <Button
          className="flex-1 rounded-field py-4"
          loading={busy}
          data-testid={`profile-${testId}-save`}
          onClick={() => onSave({ [field]: draft } as ProfileUpdate)}
        >
          Save
        </Button>
        <Button
          variant="secondary"
          disabled={busy}
          data-testid={`profile-${testId}-cancel`}
          onClick={onClose}
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}
