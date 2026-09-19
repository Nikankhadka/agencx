"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Sheet } from "@/components/ui/Sheet";
import type { BusinessProfile, ProfileUpdate } from "@/lib/api-schemas";

export interface ServicesSheetProps {
  open: boolean;
  profile: BusinessProfile;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (update: ProfileUpdate) => void;
}

/** The row's one-line summary, or the invitation to fill it. */
export function servicesSummary(profile: BusinessProfile): string {
  return profile.services.length ? profile.services.join(", ") : "Add what you offer";
}

/**
 * D28: what the business does, edited as the list it is now stored as. The
 * interview captures it one line at a time and the storefront subtitle reads it
 * back, so an owner correcting one service should not have to retype the
 * sentence around it.
 *
 * 20: a rough price may live in the line, in the owner's own words, which is
 * what the placeholder now shows. It stays their text: nothing parses it and
 * nothing quotes from it - the priced catalog is Offerings, and every amount
 * the product states comes from there through the pricing engine.
 */
export function ServicesSheet({ open, profile, busy, error, onClose, onSave }: ServicesSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} title="Edit services">
      {/* Keyed by what was loaded, like the ABN sheet: reopening starts from
          what is saved rather than from an abandoned edit. */}
      {open ? (
        <ServicesEditor
          key={profile.services.join("|")}
          profile={profile}
          busy={busy}
          error={error}
          onSave={onSave}
        />
      ) : null}
    </Sheet>
  );
}

function ServicesEditor({
  profile,
  busy,
  error,
  onSave,
}: {
  profile: BusinessProfile;
  busy: boolean;
  error: string | null;
  onSave: (update: ProfileUpdate) => void;
}) {
  const [services, setServices] = useState<string[]>(() =>
    profile.services.length ? profile.services : [""],
  );

  return (
    <div className="flex flex-col gap-4 pb-2">
      {services.map((service, index) => (
        // The index is the identity: two rows can hold the same text mid-edit,
        // and keying by value would collapse them into one.
        <div key={index} className="flex items-end gap-2">
          <div className="flex-1">
            <Input
              label={`Service ${index + 1}`}
              value={service}
              disabled={busy}
              placeholder="Screen replacement, $80 to $150"
              onChange={(event) =>
                setServices((current) =>
                  current.map((item, at) => (at === index ? event.target.value : item)),
                )
              }
            />
          </div>
          <Button
            variant="ghost"
            disabled={busy}
            aria-label={`Remove service ${index + 1}`}
            data-testid="service-remove"
            onClick={() => setServices((current) => current.filter((_, at) => at !== index))}
          >
            Remove
          </Button>
        </div>
      ))}

      <Button
        variant="secondary"
        disabled={busy}
        data-testid="service-add"
        onClick={() => setServices((current) => [...current, ""])}
      >
        Add service
      </Button>

      {error ? (
        <p role="alert" className="text-meta text-danger">
          {error}
        </p>
      ) : null}

      <Button
        className="w-full rounded-field py-4"
        loading={busy}
        data-testid="services-save"
        onClick={() => onSave({ services })}
      >
        Save
      </Button>
    </div>
  );
}
