"use client";

import { Icon } from "@/components/ui/Icon";
import type { OnboardingDraft } from "@/lib/onboarding";

/**
 * The "show-back" surface: what the assistant has captured about the business,
 * so the owner can trust and correct it. Rendered as the desktop aside and as
 * the mobile Business Sheet body. Ordered by beat so it always mirrors the
 * interview; a beat that is not yet captured shows an "awaiting" hint.
 *
 * Prices here are the owner's own stated draft figures (transcription), never
 * model-authored amounts - the deterministic pricing engine only enters the
 * picture at confirm time.
 */

type SectionValue = Record<string, unknown>;

interface SectionDef {
  key: string;
  label: string;
  render: (draft: OnboardingDraft) => string[];
}

function money(value: unknown): string | null {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return `$${value.toFixed(2)}`;
}

const POSTURE_LABELS: Record<string, string> = {
  rarely: "Escalate rarely",
  balanced: "Balanced escalation",
  cautious: "Escalate cautiously",
};

const PAYMENT_MODE_LABELS: Record<string, string> = {
  PLATFORM: "Collected through Wren",
  DIRECT: "Collected directly",
  DEFERRED: "Decide later",
};

const TERMS_LABELS: Record<string, string> = {
  deposit: "Take a deposit",
  full_before: "Full payment before",
  full_after: "Full payment after",
  later: "Decide later",
};

const CHANNEL_LABELS: Record<string, string> = {
  website: "My website",
  phone: "Phone",
  sms: "SMS",
  email: "Email",
  facebook: "Facebook",
  word_of_mouth: "Word of mouth",
};

function section(draft: OnboardingDraft, key: string): SectionValue {
  const value = draft[key];
  return value && typeof value === "object" ? value : {};
}

const SECTIONS: SectionDef[] = [
  {
    key: "business_name",
    label: "Business name",
    render: (d) => {
      const name = section(d, "business").name;
      return typeof name === "string" && name ? [name] : [];
    },
  },
  {
    key: "team",
    label: "Team",
    render: (d) => {
      const isTeam = section(d, "business").is_team;
      return typeof isTeam === "boolean" ? [isTeam ? "A team" : "Just you"] : [];
    },
  },
  {
    key: "description",
    label: "What you do",
    render: (d) => {
      const description = section(d, "identity").description;
      return typeof description === "string" && description ? [description] : [];
    },
  },
  {
    key: "hours_contact",
    label: "Hours & contact",
    render: (d) => {
      const business = section(d, "business");
      const rows: string[] = [];
      if (typeof business.hours === "string" && business.hours) rows.push(business.hours);
      if (typeof business.contact === "string" && business.contact) rows.push(business.contact);
      return rows;
    },
  },
  {
    key: "services",
    label: "Services",
    render: (d) => {
      const items = section(d, "services").items;
      if (!Array.isArray(items)) return [];
      return items.map((raw) => {
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
    render: (d) => {
      const rules = section(d, "pricing_rules").rules;
      if (!Array.isArray(rules)) return [];
      return rules.map((raw) => {
        const rule = raw as SectionValue;
        const label = typeof rule.label === "string" ? rule.label : "Rule";
        const amount = money(rule.unit_amount_dollars);
        return amount ? `${label} - ${amount}` : `${label} - amount pending`;
      });
    },
  },
  {
    key: "business_number",
    label: "Business number",
    render: (d) => {
      const tax = section(d, "tax");
      if (tax.has_business_number === false) return ["None"];
      const number = tax.business_number;
      return typeof number === "string" && number ? [number] : [];
    },
  },
  {
    key: "tax_registered",
    label: "Tax registered",
    render: (d) => {
      const registered = section(d, "tax").tax_registered;
      return typeof registered === "boolean" ? [registered ? "Yes" : "No"] : [];
    },
  },
  {
    key: "payment_mode",
    label: "Payments",
    render: (d) => {
      const mode = section(d, "payment").processing_mode;
      return typeof mode === "string" && PAYMENT_MODE_LABELS[mode]
        ? [PAYMENT_MODE_LABELS[mode]]
        : [];
    },
  },
  {
    key: "kyc",
    label: "Identity check",
    render: (d) => {
      if (section(d, "payment").processing_mode !== "PLATFORM") return [];
      const kyc = section(d, "kyc");
      if (kyc.requested) return ["ID check requested"];
      if (kyc.skipped) return ["Skipped for now"];
      return [];
    },
  },
  {
    key: "payment_terms",
    label: "Payment terms",
    render: (d) => {
      const payment = section(d, "payment");
      const terms = payment.terms;
      if (typeof terms !== "string") return [];
      const base = TERMS_LABELS[terms] ?? terms;
      if (terms === "deposit" && typeof payment.deposit_pct === "number") {
        return [`${base} - ${payment.deposit_pct}% deposit`];
      }
      return [base];
    },
  },
  {
    key: "inbound_channels",
    label: "Reach you via",
    render: (d) => {
      const channels = section(d, "business").inbound_channels;
      if (!Array.isArray(channels)) return [];
      return channels
        .map((c) => (typeof c === "string" ? (CHANNEL_LABELS[c] ?? c) : ""))
        .filter(Boolean);
    },
  },
  {
    key: "tone",
    label: "Tone",
    render: (d) => {
      const tone = section(d, "tone").tone;
      return typeof tone === "string" && tone ? [tone] : [];
    },
  },
  {
    key: "escalation_posture",
    label: "Escalation",
    render: (d) => {
      const posture = section(d, "escalation_threshold").posture;
      return typeof posture === "string" && POSTURE_LABELS[posture]
        ? [POSTURE_LABELS[posture]]
        : [];
    },
  },
];

export function ShowBack({
  draft,
  completed,
}: {
  draft: OnboardingDraft;
  completed: boolean;
}) {
  const rows = SECTIONS.map((sectionDef) => {
    const values = sectionDef.render(draft);
    return { ...sectionDef, values };
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
