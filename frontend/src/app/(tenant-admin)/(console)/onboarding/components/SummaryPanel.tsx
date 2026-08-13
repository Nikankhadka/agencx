"use client";

import { Icon } from "@/components/ui/Icon";

/**
 * Live "what's been captured" panel for onboarding. Replaces the old stage
 * pills (which looked like inputs to fill in) with a sequential flow: an
 * ordered list of sections, each showing a status glyph plus the concrete
 * values the copilot has collected, or a muted "awaiting" hint when still open.
 */

type SectionValue = Record<string, unknown>;
type Draft = Record<string, SectionValue>;

interface SectionDef {
  key: string;
  label: string;
  render: (section: SectionValue) => string[];
}

const POSTURE_LABELS: Record<string, string> = {
  rarely: "Escalate rarely",
  balanced: "Balanced escalation",
  cautious: "Escalate cautiously",
};

function money(value: unknown): string | null {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return `$${value.toFixed(2)}`;
}

const SECTIONS: SectionDef[] = [
  {
    key: "identity",
    label: "About your business",
    render: (s) => {
      const description = s.description;
      return typeof description === "string" && description ? [description] : [];
    },
  },
  {
    key: "tone",
    label: "Voice and tone",
    render: (s) => {
      const tone = s.tone;
      return typeof tone === "string" && tone ? [tone] : [];
    },
  },
  {
    key: "services",
    label: "Services and products",
    render: (s) => {
      if (!Array.isArray(s.items)) return [];
      return s.items.map((raw) => {
        const item = raw as SectionValue;
        const name = typeof item.name === "string" ? item.name : "Item";
        const price = money(item.price_dollars);
        return price ? `${name} - ${price}` : `${name} - price pending`;
      });
    },
  },
  {
    key: "pricing_rules",
    label: "Pricing rules",
    render: (s) => {
      if (!Array.isArray(s.rules)) return [];
      return s.rules.map((raw) => {
        const rule = raw as SectionValue;
        const label = typeof rule.label === "string" ? rule.label : "Rule";
        const amount = money(rule.unit_amount_dollars);
        return amount ? `${label} - ${amount}` : `${label} - amount pending`;
      });
    },
  },
  {
    key: "escalation_threshold",
    label: "Escalation",
    render: (s) => {
      const posture = s.posture;
      if (typeof posture === "string" && POSTURE_LABELS[posture]) {
        return [POSTURE_LABELS[posture]];
      }
      const threshold = s.threshold;
      if (typeof threshold === "number") return [`Threshold ${threshold}`];
      return [];
    },
  },
];

export function SummaryPanel({
  draft,
  completed,
}: {
  draft: Draft;
  completed: boolean;
}) {
  const capturedKeys = Object.keys(draft);
  const nextIndex = SECTIONS.findIndex((section) => !capturedKeys.includes(section.key));

  return (
    <div className="rounded-lg border border-border bg-surface p-4 shadow-1">
      <h2 className="text-title-3 font-semibold text-text">Your business</h2>
      {completed ? (
        <p className="mt-1.5 flex items-center gap-1.5 text-body-sm text-success">
          <Icon name="check_circle" size={16} />
          Onboarding complete - you are live.
        </p>
      ) : (
        <p className="mt-1.5 text-body-sm text-text-secondary">
          {capturedKeys.length === 0
            ? "Nothing captured yet - the copilot will guide you."
            : "Here is what we have captured so far."}
        </p>
      )}

      <ol className="mt-4 flex flex-col gap-3" aria-label="Onboarding progress">
        {SECTIONS.map((section, index) => {
          const captured = capturedKeys.includes(section.key);
          const values = captured ? section.render(draft[section.key]) : [];
          const isNext = !completed && index === nextIndex;

          return (
            <li key={section.key} className="flex items-start gap-3">
              <span
                className={[
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-footnote font-semibold",
                  captured
                    ? "bg-success-subtle text-success"
                    : isNext
                      ? "bg-accent-subtle text-accent"
                      : "bg-surface-container text-text-tertiary",
                ].join(" ")}
              >
                {captured ? <Icon name="check_circle" size={16} /> : index + 1}
              </span>

              <div className="min-w-0 flex-1">
                <p
                  className={[
                    "text-body-sm font-medium",
                    captured ? "text-text" : "text-text-secondary",
                  ].join(" ")}
                >
                  {section.label}
                </p>
                {captured ? (
                  <ul className="mt-0.5 flex flex-col gap-0.5">
                    {values.map((value, valueIndex) => (
                      <li key={valueIndex} className="text-footnote text-text-tertiary">
                        {value}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-0.5 text-footnote text-text-tertiary">
                    {isNext ? "Next up" : "Awaiting"}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
