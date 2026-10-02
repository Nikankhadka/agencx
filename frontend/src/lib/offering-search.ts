/**
 * RF-3: the client-side offering search, the same predicate the backend uses
 * (`position(lower(needle) in lower(...))` over name, description and category
 * names). Both surfaces load the catalog whole - the owner editor keeps it in
 * state for local editing, the storefront receives it as server-rendered props
 * - so filtering in memory is instant and race-free rather than a round trip
 * per keystroke. The backend `search` param is the contract for server-side
 * consumers; this keeps the two in agreement.
 */
export interface SearchableOffering {
  name: string;
  description: string;
  category?: string | null;
  categories?: Array<{ name: string }>;
}

export function offeringMatches(offering: SearchableOffering, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  const haystack = [
    offering.name,
    offering.description,
    offering.category ?? "",
    ...(offering.categories ?? []).map((category) => category.name),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(needle);
}

export function filterOfferings<T extends SearchableOffering>(
  offerings: T[],
  query: string,
): T[] {
  return offerings.filter((offering) => offeringMatches(offering, query));
}
