/**
 * The tenant-admin onboarding SSE + state protocol, mirroring the events the
 * backend emits in app/features/onboarding/api.py and the shape of
 * OnboardingStateResponse. The beat system (app/onboarding/beats.py) is the
 * single source of truth for what each widget renders; this module just types
 * the wire format and guards the one parser entry point so a malformed frame
 * never aborts an in-progress stream.
 */

export type WidgetKind = "text" | "chips" | "masked" | "cta";

export interface ChipSpec {
  label: string;
  value: string;
  /** Dashed suggestion chip - marks a multi-select beat (e.g. inbound channels). */
  dashed?: boolean;
}

export interface InputSpec {
  kind: WidgetKind;
  placeholder: string;
  chips: ChipSpec[];
  mask: string | null;
  cta_label: string | null;
}

/** The captured draft: one object per section, keyed by section name. */
export type OnboardingDraft = Record<string, Record<string, unknown>>;

export interface OnboardingState {
  /** The current beat key, or "confirm" when every beat is satisfied. */
  stage: string;
  /** Last assistant message (kept for older clients; prefer history[]). */
  prompt: string;
  draft: OnboardingDraft;
  completed: boolean;
  history: { role: string; content: string }[];
  /** The composer widget for the current beat, or null once complete. */
  input: InputSpec | null;
  can_confirm: boolean;
}

export type OnboardingStreamEvent =
  | { type: "progress"; stage: string }
  | { type: "token"; text: string }
  | { type: "redraft"; reason?: string }
  | { type: "reply"; text: string }
  | {
      type: "state";
      stage: string;
      draft: OnboardingDraft;
      completed: boolean;
      input: InputSpec | null;
      can_confirm: boolean;
    }
  | { type: "done" }
  | { type: "error"; detail?: string };

/**
 * Parse one onboarding SSE `data:` payload into a typed event, or `null` when
 * it is not valid JSON with a string `type`. Returning `null` (rather than
 * throwing) lets the caller skip a bad frame and keep reading the stream.
 */
export function parseOnboardingEvent(payload: string): OnboardingStreamEvent | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch {
    return null;
  }
  if (
    parsed !== null &&
    typeof parsed === "object" &&
    typeof (parsed as { type?: unknown }).type === "string"
  ) {
    return parsed as OnboardingStreamEvent;
  }
  return null;
}

/** True when a beat's chips carry the dashed multi-select marker. */
export function isMultiSelect(input: InputSpec): boolean {
  return input.kind === "chips" && input.chips.some((chip) => chip.dashed);
}

/**
 * Fold one stream event into the in-progress assistant reply. ``token``
 * deltas accumulate (the typewriter); ``redraft`` clears them so the client
 * drops the rejected draft before the replacement streams in (the price-echo
 * guard tripped); ``reply`` is the full text the backend also emits for older
 * clients, so it reconciles to the same string the tokens built.
 */
export function foldReply(reply: string, event: OnboardingStreamEvent): string {
  switch (event.type) {
    case "token":
      return reply + event.text;
    case "redraft":
      return "";
    case "reply":
      return event.text;
    default:
      return reply;
  }
}
