"use client";

import { Icon } from "@/components/ui/Icon";
import type { OnboardingDraft } from "@/lib/onboarding";

/**
 * The "show-back" surface: what the assistant has captured about the business,
 * so the owner can trust and correct it. Rendered as the desktop aside and as
 * the mobile Business Sheet body. Ordered by beat so it always mirrors the
 * interview; a field that is not yet captured shows an "awaiting" hint.
 *
 * The rows mirror BEAT_ORDER in app/onboarding/beats.py - one per lean profile
 * field. Nothing here branches on a business vertical (I8): business type is
 * one more captured line, not a switch.
 */

/** One row per lean profile field, in beat order. */
const FIELDS: { key: string; label: string }[] = [
  { key: "name", label: "Your name" },
  { key: "business_name", label: "Business name" },
  { key: "business_type", label: "Business type" },
  { key: "headcount", label: "Team" },
  { key: "hours", label: "Opening hours" },
  { key: "services", label: "What you offer" },
  { key: "contact", label: "Contact" },
];

export function ShowBack({
  draft,
  completed,
}: {
  draft: OnboardingDraft;
  completed: boolean;
}) {
  const rows = FIELDS.map((field) => {
    const value = draft[field.key];
    return { ...field, values: value ? [value] : [] };
  });
  const capturedCount = rows.filter((row) => row.values.length > 0).length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-title-3 font-semibold text-text">Your business</h2>
        {completed ? (
          <span className="flex items-center gap-1.5 text-footnote text-success">
            <Icon name="check_circle" size={16} />
            Live
          </span>
        ) : (
          <span className="text-footnote text-text-tertiary">
            {capturedCount}/{rows.length} captured
          </span>
        )}
      </div>

      <ol className="flex flex-col gap-3" aria-label="Onboarding progress" data-testid="show-back">
        {rows.map((row) => {
          const captured = row.values.length > 0;
          return (
            <li key={row.key} className="flex items-start gap-3">
              <span
                className={[
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-footnote font-semibold",
                  captured
                    ? "bg-success-subtle text-success"
                    : "bg-surface-container text-text-tertiary",
                ].join(" ")}
              >
                {captured ? <Icon name="check_circle" size={16} /> : <span aria-hidden="true" />}
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className={[
                    "text-body-sm font-medium",
                    captured ? "text-text" : "text-text-secondary",
                  ].join(" ")}
                >
                  {row.label}
                </p>
                {captured ? (
                  <ul className="mt-0.5 flex flex-col gap-0.5">
                    {row.values.map((value, index) => (
                      <li key={index} className="text-footnote text-text-tertiary">
                        {value}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-0.5 text-footnote text-text-tertiary">Awaiting</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
