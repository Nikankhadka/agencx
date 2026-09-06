/**
 * The tenant-admin onboarding SSE + state protocol, mirroring the events the
 * backend emits in app/features/onboarding/api.py and the shape of
 * OnboardingStateResponse. The beat system (app/onboarding/beats.py) is the
 * single source of truth for what each widget renders; this module just types
 * the wire format and guards the one parser entry point so a malformed frame
 * never aborts an in-progress stream.
 */

export type WidgetKind = "text" | "chips" | "masked" | "cta" | "phone";

export interface ChipSpec {
  label: string;
  value: string;
  /**
   * Dashed suggestion chip (the prototype's `.c-suggest`). A style, not a
   * behaviour: O-6 uses it to mark a chip that opens a different input rather
   * than answering outright. It used to mean "multi-select"; nothing is
   * multi-select any more, and the helper that read it this way is gone.
   */
  dashed?: boolean;
  /**
   * O-6: tapping this chip swaps the composer to that widget instead of
   * submitting its label. The country-code phone pill and the ABN pill both
   * arrive this way, so the client never has to know which beat it is on.
   */
  widget?: WidgetKind | null;
}

export interface InputSpec {
  kind: WidgetKind;
  placeholder: string;
  chips: ChipSpec[];
  mask: string | null;
  cta_label: string | null;
  /** O-6: the label welded inside the pill's left edge (the prototype's `.abn-pre`). */
  prefix?: string | null;
  /**
   * O-6: prepend a one-tap chip carrying the address the owner logged in with.
   * The server declares that the chip belongs here but cannot supply it - the
   * address lives in Supabase auth, and the client already holds it in session.
   */
  suggest_owner_email?: boolean;
}

/**
 * The captured business profile: one string per field, keyed by field name
 * (O-1 - the flat draft that replaced the per-section objects).
 */
export type OnboardingDraft = Record<string, string>;

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
  suggested_slug: string | null;
  paused_beat: string | null;
  offering_candidates?: {
    name: string;
    description: string;
    price_cents: number | null;
    sources: ("owner" | "document")[];
  }[];
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
      suggested_slug: string | null;
      paused_beat: string | null;
      offering_candidates?: OnboardingState["offering_candidates"];
    }
  | { type: "done" }
  | { type: "error"; code: string; detail: string; request_id: string };

/**
 * Parse one onboarding SSE `data:` payload into a typed event, or `null` when
 * it is not valid JSON with a string `type`. Returning `null` (rather than
 * throwing) lets the caller skip a bad frame and keep reading the stream.
 */
export function parseOnboardingEvent(
  payload: string,
): OnboardingStreamEvent | null {
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

/**
 * What the backend's knowledge upload accepts (`ALLOWED_EXTENSIONS` in
 * app/features/knowledge/api.py). Checked here so an unusable file is answered
 * in one line by the assistant rather than by a 422 the owner has to interpret.
 */
export const ACCEPTED_UPLOAD_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".md",
  ".txt",
  ".csv",
  ".json",
] as const;

/** Extensions worth naming in the refusal - the owner reached for a photo. */
const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".heic", ".webp", ".gif"];

export interface UploadVerdict {
  accepted: boolean;
  /** One calm line for the thread - an acknowledgement, or the reason it can't be read. */
  message: string;
}

function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot).toLowerCase();
}

/**
 * The assistant's line for one attached file, decided before the upload starts.
 *
 * Images are refused, not queued: nothing in the stack reads one (no OCR, no
 * vision call), so accepting a photo of a menu would promise an answer that
 * never comes. Every refusal names the way forward, and never blocks the
 * interview - knowledge can be added later from Settings > Knowledge.
 */
export function describeUpload(filename: string): UploadVerdict {
  const ext = extensionOf(filename);
  if ((ACCEPTED_UPLOAD_EXTENSIONS as readonly string[]).includes(ext)) {
    return {
      accepted: true,
      message: `Got your ${filename} - I'll answer from it now.`,
    };
  }
  if (IMAGE_EXTENSIONS.includes(ext)) {
    return {
      accepted: false,
      message: `I can't read images yet, so ${filename} won't help me answer. A PDF, a document, or a link to the page works.`,
    };
  }
  return {
    accepted: false,
    message: `I can't read ${filename || "that file"}. A PDF, a document, or a link to the page works.`,
  };
}
