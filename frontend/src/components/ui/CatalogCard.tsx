import { Card } from "./Card";
import { formatCents } from "@/lib/money";

export interface CatalogOffering {
  id: string;
  name: string;
  description: string;
  category: string | null;
  categories?: Array<{ id: string; name: string; position: number; is_primary: boolean }>;
  price_cents: number | null;
  /** RF-4: display-only pricing wording, used when there is no fixed price. */
  pricing_wording?: string | null;
}

export interface CatalogPayload {
  offerings: CatalogOffering[];
}

/**
 * The card is a view of the catalog, not the catalog: a 96-item shop would
 * otherwise fill the chat. Each category shows its first rows and a "+N more"
 * line; the assistant can still name any item in its text.
 */
export const CATALOG_CARD_ROWS_PER_CATEGORY = 5;

export function CatalogCard({ catalog }: { catalog: CatalogPayload }) {
  const groups: Array<[string, CatalogOffering[]]> = [];
  for (const offering of catalog.offerings) {
    const headings = offering.categories?.length
      ? offering.categories.map((category) => category.name)
      : [offering.category?.trim() || "Offerings"];
    for (const heading of headings) {
      const group = groups.find(([name]) => name === heading);
      if (group && !group[1].some((item) => item.id === offering.id)) group[1].push(offering);
      else if (!group) groups.push([heading, [offering]]);
    }
  }

  return (
    <Card aria-label="Catalog" className="mt-2 w-full max-w-[520px]">
      <h3 className="mb-3 text-body font-semibold text-text">Current offerings</h3>
      <div className="flex flex-col gap-4">
        {groups.map(([heading, offerings]) => (
          <section key={heading}>
            <h4 className="mb-1 text-footnote font-semibold uppercase text-text-secondary">
              {heading}
            </h4>
            <ul>
              {offerings.slice(0, CATALOG_CARD_ROWS_PER_CATEGORY).map((offering) => (
                <li key={offering.id} className="border-b border-hairline py-2 last:border-0">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-medium text-text">{offering.name}</span>
                    <span className="shrink-0 tabular-nums text-body-sm text-text">
                      {offering.price_cents !== null
                        ? formatCents(offering.price_cents)
                        : offering.pricing_wording?.trim() || "Price not listed"}
                    </span>
                  </div>
                  {offering.description ? (
                    <p className="mt-1 text-body-sm text-text-secondary">{offering.description}</p>
                  ) : null}
                </li>
              ))}
            </ul>
            {offerings.length > CATALOG_CARD_ROWS_PER_CATEGORY ? (
              <p className="pt-2 text-footnote text-text-secondary">
                +{offerings.length - CATALOG_CARD_ROWS_PER_CATEGORY} more
              </p>
            ) : null}
          </section>
        ))}
      </div>
    </Card>
  );
}
