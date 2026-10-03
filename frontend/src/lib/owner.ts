/**
 * RF-7: whether the signed-in viewer owns the storefront being rendered.
 *
 * Pure and server-agnostic so the owner-match rule is unit-testable without a
 * request: `resolveViewerSlug` reads the session and the backend, this decides.
 * It is UX gating only - the backend bearer check and RLS are the enforcement
 * boundary, so a false negative only hides edit controls, never leaks data.
 */
export function isStorefrontOwner(
  viewerSlug: string | null | undefined,
  slug: string,
): boolean {
  return typeof viewerSlug === "string" && viewerSlug === slug;
}
