/**
 * Tenant brand mark: the tenant's logo when set, otherwise a monogram avatar
 * (first letter of the display name on the accent color). Used by the customer
 * chat header and the tenant-admin console sidebar. bg-accent is AA-safe in
 * both places: the customer surface only injects a tenant accent when it
 * passes WCAG AA against the light surface (brand.ts), and the console falls
 * back to the default accent ramp which passes too.
 */
export function BrandMark({ logoUrl, name }: { logoUrl?: string | null; name: string }) {
  if (logoUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- tenant-supplied, unknown dimensions
      <img src={logoUrl} alt="" className="h-8 w-8 rounded-full object-cover" />
    );
  }
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span
      aria-hidden
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-body-sm font-semibold text-text-inverse"
    >
      {initial}
    </span>
  );
}