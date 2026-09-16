/**
 * Tenant brand mark: the tenant's logo when set, otherwise a monogram avatar
 * (first letter of the display name on the Airbnb CTA gradient in inverse
 * text). Used by the customer chat header and the tenant-admin console
 * sidebar. The gradient is fixed - the tenant's stored accent is no longer
 * injected (D25); the white initial passes AA on every gradient stop (D26).
 * `size` picks the box: "sm" (32px) for headers, "lg" (56px) for the M-7
 * storefront hero identity.
 */
export function BrandMark({
  logoUrl,
  name,
  size = "sm",
}: {
  logoUrl?: string | null;
  name: string;
  size?: "sm" | "lg";
}) {
  const box = size === "lg" ? "h-14 w-14 text-title-2" : "h-8 w-8 text-body-sm";
  if (logoUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- tenant-supplied, unknown dimensions
      <img src={logoUrl} alt="" className={`${box} rounded-full object-cover`} />
    );
  }
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-full bg-brand font-semibold text-text-inverse ${box}`}
    >
      {initial}
    </span>
  );
}