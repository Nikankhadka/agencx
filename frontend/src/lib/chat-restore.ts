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
 */
export type ChatCardResponse =
  | { type: "quote"; quote: QuotePayload }
  | { type: "price_summary"; summary: PriceSummaryPayload }
  | { type: "catalog"; catalog: CatalogPayload };

export interface ChatCards {
  quote?: QuotePayload;
  priceSummary?: PriceSummaryPayload;
  catalog?: CatalogPayload;
}

/** The card payload a bubble renders, or `{}` for an unknown/missing one. */
export function cardFromResponse(response: unknown): ChatCards {
  if (!isPayload(response)) return {};
  const candidate = response as {
    type?: unknown;
    quote?: unknown;
    summary?: unknown;
    catalog?: unknown;
  };
  switch (candidate.type) {
    case "quote":
      return isPayload(candidate.quote) ? { quote: candidate.quote as QuotePayload } : {};
    case "price_summary":
      return isPayload(candidate.summary)
        ? { priceSummary: candidate.summary as PriceSummaryPayload }
        : {};
    case "catalog":
      return isPayload(candidate.catalog) ? { catalog: candidate.catalog as CatalogPayload } : {};
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

function isPayload(value: unknown): boolean {
  return value !== null && typeof value === "object";
}
