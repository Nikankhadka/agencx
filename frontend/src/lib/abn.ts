/**
 * O-6/O-9: the ABN, in the two places it is seen.
 *
 * The interview's masked pill and the Settings row both render the same eleven
 * digits, so the grouping lives here rather than in either screen. The stored
 * value is always the digits themselves (or the `NO_ABN` sentinel) - formatting
 * is what a screen does to them, never what is written down.
 */

/** The stated answer of an owner who does not have an ABN (backend `NO_ABN`). */
export const NO_ABN = "none";

/**
 * The prototype's `XX XXX XXX XXX` mask, grouped as the owner types and capped
 * at eleven digits. Anything that is not a digit is dropped, so a value that
 * arrives already formatted is idempotent.
 */
export function formatAbn(value: string): string {
  const d = value.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d;
  if (d.length <= 5) return `${d.slice(0, 2)} ${d.slice(2)}`;
  if (d.length <= 8) return `${d.slice(0, 2)} ${d.slice(2, 5)} ${d.slice(5)}`;
  return `${d.slice(0, 2)} ${d.slice(2, 5)} ${d.slice(5, 8)} ${d.slice(8)}`;
}

/**
 * Registered unless the owner said otherwise. The interview stores "yes"/"no",
 * but it is an extracted field, so the chip labels it was extracted from
 * ("Not yet") are read here too rather than trusted to have been normalized.
 */
export function isGstRegistered(value: string): boolean {
  return ["yes", "y", "true", "registered"].includes(value.trim().toLowerCase());
}

/**
 * The prototype's settings summary line (`setSummary('abn')`):
 * `51 824 753 556 · GST registered`. An owner without an ABN was never asked
 * about GST, so their line does not answer a question they never heard.
 */
export function abnSummary(profile: { abn: string; gst: string }): string {
  const abn = profile.abn.trim();
  if (!abn) return "Not set";
  if (abn.toLowerCase() === NO_ABN) return "No ABN";
  return `${formatAbn(abn)} · ${isGstRegistered(profile.gst) ? "GST registered" : "Not GST registered"}`;
}
