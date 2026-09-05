/**
 * W-4 US-3: client-side mirror of the tenant slug shape rule, so an owner
 * gets an actionable message before the round trip to the backend's 422
 * rather than only after it. Mirrors
 * backend/app/features/tenants/slug.py:16-19 (the pattern) and :53-65
 * (`validate_slug`'s shape/length checks) - not the reserved-name check
 * (see the ponytail note below). Backend validation stays authoritative;
 * this only front-loads the same checks for earlier, clearer feedback.
 *
 * ponytail: SLUG_PATTERN/SLUG_MIN_LENGTH/SLUG_MAX_LENGTH are a hand-kept
 * copy of the same three constants in slug.py - two languages, no shared
 * file, so they can drift. The upgrade path, if that ever actually bites, is
 * a checked-in JSON both sides read (same shape as reserved-slugs.test.ts's
 * own note on RESERVED_SLUGS, which this module deliberately does not
 * duplicate - the server's specific "that name is reserved" message stays
 * the one copy of that list).
 */
const SLUG_PATTERN = /^[a-z0-9](-?[a-z0-9])*$/;
const SLUG_MIN_LENGTH = 3;
const SLUG_MAX_LENGTH = 40;

/**
 * Returns an owner-readable reason `value` cannot be a page address, or
 * `null` when the shape is fine. Checked in the order that gives the most
 * useful message first: an empty field is told to enter an address rather
 * than shown a length or pattern complaint, and length is checked before
 * shape since "too short" or "too long" is a plainer fix than parsing a
 * pattern violation.
 */
export function slugShapeError(value: string): string | null {
  if (!value) return "Enter a page address.";
  if (value.length < SLUG_MIN_LENGTH) {
    return `Page address must be at least ${SLUG_MIN_LENGTH} characters.`;
  }
  if (value.length > SLUG_MAX_LENGTH) {
    return `Page address must be ${SLUG_MAX_LENGTH} characters or fewer.`;
  }
  if (!SLUG_PATTERN.test(value)) {
    return "Page address can only use lowercase letters, numbers, and single dashes between them.";
  }
  return null;
}
