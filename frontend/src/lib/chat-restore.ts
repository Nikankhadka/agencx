import type { ChatRole } from "@/components/ui/ChatBubble";
import type { QuotePayload } from "@/components/ui/QuoteCard";
import type { PriceSummaryPayload } from "@/components/ui/PriceSummaryCard";
import type { CatalogPayload } from "@/components/ui/CatalogCard";
import type { PublicMessage } from "./api-schemas";

/**
 * RF-12: turn a restored `PublicMessage.response` back into the card a bubble
 * shows. The backend exposes exactly one card payload per assistant turn - a
 * formal quote, a price summary, or a catalog - with a `type` discriminator,
 * or nothing at all for a plain text turn.
 *
 * Kept browser-free and pure so it is unit-testable: the repository has no
 * jsdom, so restore behaviour that lived in the component effect would only be
 * covered by E2E. Anything malformed returns no cards rather than throwing -
 * a bad stored row must degrade to the plain transcript, never brick the chat.
 * That includes shape checks the cards would otherwise crash on: each payload
 * must carry the array its card iterates (``line_items`` / ``offerings``), and
 * an array is never a valid card object.
 */
export interface ChatCards {
  quote?: QuotePayload;
  priceSummary?: PriceSummaryPayload;
  catalog?: CatalogPayload;
}

/** The card payload a bubble renders, or `{}` for an unknown/missing one. */
export function cardFromResponse(response: unknown): ChatCards {
  const candidate = asRecord(response);
  if (!candidate) return {};
  switch (candidate.type) {
    case "quote": {
      const quote = asRecord(candidate.quote);
      return quote && Array.isArray(quote.line_items)
        ? { quote: quote as unknown as QuotePayload }
        : {};
    }
    case "price_summary": {
      const summary = asRecord(candidate.summary);
      return summary && Array.isArray(summary.line_items)
        ? { priceSummary: summary as unknown as PriceSummaryPayload }
        : {};
    }
    case "catalog": {
      const catalog = asRecord(candidate.catalog);
      return catalog && Array.isArray(catalog.offerings)
        ? { catalog: catalog as unknown as CatalogPayload }
        : {};
    }
    default:
      return {};
  }
}

/** A restored transcript row as the chat's message shape. */
export interface RestoredMessage {
  role: ChatRole;
  text: string;
  quote?: QuotePayload;
  priceSummary?: PriceSummaryPayload;
  catalog?: CatalogPayload;
}

export function messageFromPublic(m: PublicMessage): RestoredMessage {
  return {
    role: m.role as ChatRole,
    text: m.content,
    ...cardFromResponse(m.response),
  };
}

/** A plain object, never null and never an array (an array is not a card). */
function asRecord(value: unknown): Record<string, unknown> | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}
