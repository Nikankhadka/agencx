import { CatalogCard, type CatalogPayload } from "./CatalogCard";
import { PriceSummaryCard, type PriceSummaryPayload } from "./PriceSummaryCard";

/**
 * The owner transcript payload carries one card, never a tenant slug. The slug
 * stays a prop (a payload field would freeze the storefront address into every
 * assistant turn), so an owner transcript renders the bounded card without the
 * page link.
 */
export function StructuredResponse({ response, slug }: { response: unknown; slug?: string }) {
  if (!response || typeof response !== "object") return null;
  const value = response as {
    type?: unknown;
    summary?: unknown;
    catalog?: unknown;
  };
  if (value.type === "price_summary") {
    return <PriceSummaryCard summary={value.summary as PriceSummaryPayload} />;
  }
  if (value.type === "catalog") {
    return <CatalogCard catalog={value.catalog as CatalogPayload} slug={slug ?? ""} />;
  }
  return null;
}
