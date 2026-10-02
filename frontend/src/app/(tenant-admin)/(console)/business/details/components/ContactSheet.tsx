"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { PhonePill } from "@/components/ui/PhonePill";
import { Sheet } from "@/components/ui/Sheet";
import type { BusinessProfile, ProfileUpdate } from "@/lib/api-schemas";

export interface ContactSheetProps {
  open: boolean;
  profile: BusinessProfile;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (update: ProfileUpdate) => void;
}

/**
 * RF-2: the business contact, one value behind one field. The "Phone number"
 * button next to Save swaps the free-text field for the country-code PhonePill;
 * the pill is controlled and has no send circle, so Save is the only submit,
 * and the button flips to "Email" to bring the text field back.
 */
export function ContactSheet({ open, profile, busy, error, onClose, onSave }: ContactSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} title="Edit business contact">
      {/* Keyed by what was saved: reopening starts from the saved value. */}
      {open ? (
        <ContactEditor
          key={profile.business_contact}
          profile={profile}
          busy={busy}
          error={error}
          onClose={onClose}
          onSave={onSave}
        />
      ) : null}
    </Sheet>
  );
}

function ContactEditor({
  profile,
  busy,
  error,
  onClose,
  onSave,
}: Omit<ContactSheetProps, "open">) {
  const [detail, setDetail] = useState(profile.business_contact);
  const [phoneMode, setPhoneMode] = useState(false);
  const fieldClass =
    "w-full rounded-field border border-border bg-surface px-4 py-3 text-field text-text outline-none transition-colors duration-(--duration-fast) placeholder:text-ink-a40 focus:border-text disabled:opacity-50";

  return (
    <div className="flex flex-col gap-4 pb-2">
      <div>
        <span className="mb-2 block text-label font-medium uppercase text-ink-a40">
          Business contact
        </span>
        {phoneMode ? (
          <PhonePill
            disabled={busy}
            value={detail}
            onChange={setDetail}
            showSubmit={false}
            testId="contact-phone-input"
          />
        ) : (
          <input
            value={detail}
            onChange={(event) => setDetail(event.target.value)}
            placeholder="Email, address, or phone"
            aria-label="Business contact"
            disabled={busy}
            autoFocus
            data-testid="contact-detail-input"
            className={fieldClass}
          />
        )}
      </div>

      <button
        type="button"
        disabled={busy}
        aria-pressed={phoneMode}
        data-testid="contact-phone-toggle"
        onClick={() => setPhoneMode((on) => !on)}
        className="min-h-11 self-start px-2 text-body-sm text-text transition-colors duration-(--duration-fast) hover:underline active:opacity-60 disabled:opacity-50"
      >
        {phoneMode ? "Email" : "Phone number"}
      </button>

      {error ? (
        <p role="alert" className="text-meta text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex gap-2">
        <Button
          className="flex-1 rounded-field py-4"
          loading={busy}
          data-testid="contact-save"
          onClick={() => onSave({ business_contact: detail })}
        >
          Save
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          data-testid="contact-cancel"
          onClick={onClose}
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}
