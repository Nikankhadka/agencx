"use client";

import { useState } from "react";
import { Chip } from "@/components/ui/Chip";
import { Button } from "@/components/ui/Button";
import {
  buildSellingModePayload,
  confirmationCopy,
  MODE_ORDER,
  MODE_TITLES,
  rowsFor,
  type AcceptanceMode,
  type AxisKey,
  type Capabilities,
  type FulfillmentMode,
  type Mode,
  type PaymentMode,
  type ScheduleMode,
  type SellingModePayload,
  type SellingModeSuggestion,
  type StockMode,
} from "@/lib/selling-modes";

/**
 * 32: the one selling-mode question, as a card under the assistant's question.
 *
 * Two states, both server-driven:
 *
 * 1. **Confirm** - the inference's own sentence, the evidence it scored, and
 *    the summary the server rendered from the config. High confidence is one
 *    tap; medium asks which of two; low offers all four.
 * 2. **Change** - the four modes as a multi-select, then only the follow-ups the
 *    picked modes actually have. Every row already shows its default, so the
 *    owner can skip all of them and just save.
 *
 * Only the confirm view repeats the inference. The change view drops that
 * sentence the moment the owner starts editing, because it describes the guess
 * rather than the config being built; the authoritative sentence is the one the
 * confirm screen renders from what was stored.
 *
 * The write is one POST and the state it answers with is applied directly, so
 * a lost response costs a retry and nothing else. The card never computes the
 * summary and never names a trade. Every string that names an item, a
 * collection, or an action comes from the label map.
 */

export interface SellingModeCardProps {
  suggestion: SellingModeSuggestion;
  busy: boolean;
  /**
   * Which view the card opens on.
   *
   * The interview opens it on "confirm" - the inference's sentence with a
   * one-tap yes. The confirm screen's [Edit] opens it on "change", because the
   * owner is already editing the config that screen showed them.
   */
  initialView?: "confirm" | "change";
  /** Write the mode. Resolves once the parent has taken the server's state. */
  onSave: (payload: SellingModePayload) => Promise<void>;
}

const FULFILLMENT_OPTIONS: { value: FulfillmentMode; label: string }[] = [
  { value: "in_house", label: "Eat in" },
  { value: "pickup", label: "Pickup" },
  { value: "delivery", label: "Delivery" },
  { value: "onsite", label: "Come to them" },
  { value: "shipping", label: "Shipping" },
];

const SCHEDULE_OPTIONS: { value: ScheduleMode; label: string }[] = [
  { value: "asap", label: "As soon as possible" },
  { value: "slot", label: "A time slot" },
  { value: "window", label: "A visit window" },
  { value: "none", label: "No time promised" },
];

const STOCK_OPTIONS: { value: StockMode; label: string }[] = [
  { value: "none", label: "No" },
  { value: "flag", label: "Sold out only" },
  { value: "counted", label: "Count them" },
];

const ACCEPTANCE_OPTIONS: { value: AcceptanceMode; label: string }[] = [
  { value: "auto", label: "Accept automatically" },
  { value: "owner", label: "I approve each one" },
  { value: "deposit", label: "Deposit first" },
];

const PAYMENT_OPTIONS: { value: PaymentMode; label: string }[] = [
  { value: "now", label: "Pay up front" },
  { value: "later", label: "Pay later" },
  { value: "deposit", label: "Deposit" },
];

/** How long an order takes. The value is `defaults.lead_time_minutes`. */
const LEAD_TIME_OPTIONS = [15, 30, 45] as const;

const ROW_QUESTION: Record<AxisKey, string> = {
  fulfillment: "How do they get it?",
  schedule: "Do customers pick a time?",
  stock: "Do you run out of items?",
  acceptance: "Do you approve each one?",
  payment: "When do they pay?",
  lead_time: "How long does an order take?",
};

function toggle<T>(values: T[], value: T): T[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function SellingModeCard({
  suggestion,
  busy,
  initialView = "confirm",
  onSave,
}: SellingModeCardProps) {
  // 32: start from the config in the payload, not from a preset. Before the
  // question is answered that is the mode's own bundle; on the confirm
  // screen's edit it is the stored one, so the rows open on what was saved.
  const initialModes: Mode[] =
    suggestion.capabilities.sell.length > 0
      ? suggestion.capabilities.sell
      : suggestion.candidates.length > 0
        ? [suggestion.candidates[0]!]
        : [MODE_ORDER[0]!];
  const [mode, setMode] = useState<"confirm" | "change">(initialView);
  const [picked, setPicked] = useState<Mode[]>(initialModes);
  const [axes, setAxes] = useState<Capabilities>(() => ({
    ...suggestion.capabilities,
    sell: [...initialModes],
  }));
  const [leadTime, setLeadTime] = useState<number>(
    Number(suggestion.defaults?.lead_time_minutes ?? 30),
  );
  const [error, setError] = useState<string | null>(null);

  const copy = confirmationCopy(suggestion);
  const labels = suggestion.labels;
  const rows = rowsFor(picked);

  /** Toggle one mode; the last one stays picked because empty is not an answer. */
  function pickMode(value: Mode) {
    const toggled = toggle(picked, value);
    const next = toggled.length > 0 ? toggled : [value];
    setPicked(next);
    setAxes(buildSellingModePayload(next).capabilities);
  }

  async function save(modes: Mode[] = picked) {
    setError(null);
    try {
      await onSave(
        buildSellingModePayload(modes, axes, { lead_time_minutes: leadTime }),
      );
    } catch {
      setError("I couldn't save that. Try again.");
    }
  }

  return (
    <div
      data-testid="selling-mode-card"
      className="animate-beat-in flex flex-col gap-3 rounded-card border border-hairline bg-surface p-4 shadow-card"
    >
      {mode === "confirm" ? (
        <>
          <p className="text-card-hl font-medium text-text" data-testid="selling-mode-headline">
            {copy.headline}
          </p>

          {/* The inference's own sentence, and only while the owner is answering
              it. The change view drops it: the moment a mode is picked these
              lines stop describing the config, and the authoritative sentence is
              the one the confirm screen renders from what was stored. */}
          <p className="text-prose text-text" data-testid="selling-mode-summary">
            {suggestion.summary}
          </p>

          {suggestion.evidence.length > 0 ? (
            <ul
              className="flex flex-col gap-1 text-meta text-ink-a40"
              data-testid="selling-mode-evidence"
            >
              {suggestion.evidence.map((signal) => (
                <li key={signal}>{signal}</li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}

      {mode === "confirm" ? (
        <div className="flex flex-wrap gap-2">
          {copy.confirm ? (
            <Chip
              label={copy.confirm}
              data-testid="selling-mode-confirm"
              disabled={busy}
              onClick={() => void save([suggestion.mode])}
            />
          ) : null}
          {copy.choices.map((choice) => (
            <Chip
              key={choice}
              label={MODE_TITLES[choice]}
              data-testid={`selling-mode-choice-${choice}`}
              disabled={busy}
              onClick={() => void save([choice])}
            />
          ))}
          <Chip
            label={copy.change}
            dashed
            data-testid="selling-mode-change"
            disabled={busy}
            onClick={() => {
              setAxes(buildSellingModePayload(picked).capabilities);
              setMode("change");
            }}
          />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <p className="text-meta text-ink-a40">What do customers do?</p>
            <div className="flex flex-wrap gap-2">
              {MODE_ORDER.map((choice) => (
                <Chip
                  key={choice}
                  label={MODE_TITLES[choice]}
                  selected={picked.includes(choice)}
                  data-testid={`selling-mode-pick-${choice}`}
                  disabled={busy}
                  onClick={() => pickMode(choice)}
                />
              ))}
            </div>
          </div>

          {/* Only the follow-ups the picked modes have. A single mode shows that
              mode's questions; two show the union in a fixed order. */}
          {rows.map((axis) => (
            <div key={axis} className="flex flex-col gap-2">
              <p className="text-meta text-ink-a40">
                {axis === "stock" ? `Do you run out of ${labels.items.toLowerCase()}?` : ROW_QUESTION[axis]}
              </p>
              <div className="flex flex-wrap gap-2">
                {axis === "fulfillment"
                  ? FULFILLMENT_OPTIONS.map((option) => (
                      <Chip
                        key={option.value}
                        label={option.label}
                        selected={axes.fulfillment.includes(option.value)}
                        data-testid={`selling-mode-fulfillment-${option.value}`}
                        disabled={busy}
                        onClick={() => {
                          const next = toggle(axes.fulfillment, option.value);
                          // One way in is the floor: an empty list is not an
                          // answer, so the last selected option cannot go.
                          if (next.length > 0) setAxes({ ...axes, fulfillment: next });
                        }}
                      />
                    ))
                  : null}
                {axis === "schedule"
                  ? SCHEDULE_OPTIONS.map((option) => (
                      <Chip
                        key={option.value}
                        label={option.label}
                        selected={axes.schedule === option.value}
                        data-testid={`selling-mode-schedule-${option.value}`}
                        disabled={busy}
                        onClick={() => setAxes({ ...axes, schedule: option.value })}
                      />
                    ))
                  : null}
                {axis === "stock"
                  ? STOCK_OPTIONS.map((option) => (
                      <Chip
                        key={option.value}
                        label={option.label}
                        selected={axes.stock === option.value}
                        data-testid={`selling-mode-stock-${option.value}`}
                        disabled={busy}
                        onClick={() => setAxes({ ...axes, stock: option.value })}
                      />
                    ))
                  : null}
                {axis === "acceptance"
                  ? ACCEPTANCE_OPTIONS.map((option) => (
                      <Chip
                        key={option.value}
                        label={option.label}
                        selected={axes.acceptance === option.value}
                        data-testid={`selling-mode-acceptance-${option.value}`}
                        disabled={busy}
                        onClick={() => setAxes({ ...axes, acceptance: option.value })}
                      />
                    ))
                  : null}
                {axis === "payment"
                  ? PAYMENT_OPTIONS.map((option) => (
                      <Chip
                        key={option.value}
                        label={option.label}
                        selected={axes.payment === option.value}
                        data-testid={`selling-mode-payment-${option.value}`}
                        disabled={busy}
                        onClick={() => setAxes({ ...axes, payment: option.value })}
                      />
                    ))
                  : null}
                {axis === "lead_time"
                  ? LEAD_TIME_OPTIONS.map((minutes) => (
                      <Chip
                        key={minutes}
                        label={`${minutes} minutes`}
                        selected={leadTime === minutes}
                        data-testid={`selling-mode-lead-time-${minutes}`}
                        disabled={busy}
                        onClick={() => setLeadTime(minutes)}
                      />
                    ))
                  : null}
              </div>
            </div>
          ))}

          <div>
            <Button onClick={() => void save()} loading={busy} data-testid="selling-mode-save">
              Save
            </Button>
          </div>
        </div>
      )}

      {error ? (
        <p role="status" className="text-meta text-danger" data-testid="selling-mode-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
