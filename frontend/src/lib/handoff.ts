/**
 * RF-11: pure helpers for the customer-initiated "Ask for a person" control.
 *
 * Kept free of React and the DOM so the two decisions the control makes - what
 * to post and when to offer itself - are unit-testable without a browser. The
 * repository has no jsdom, so behaviour that lives in an effect or an event
 * handler would otherwise only be covered by E2E.
 */

/**
 * The body for `POST /api/chat/handoff`. `conversation_id` is omitted, not set
 * to null, when there is none yet: the endpoint creates the conversation, so a
 * customer can ask for a person before typing anything.
 */
export function handoffRequestBody(
  slug: string,
  conversationId: string | null,
): { slug: string; conversation_id?: string } {
  return conversationId ? { slug, conversation_id: conversationId } : { slug };
}

/**
 * Whether the control should be offered at all. It is hidden once a limit stop
 * ends the conversation (the composer is replaced by the banner) and once a
 * handoff is already open, so a customer cannot fire it repeatedly. It is never
 * gated on whether contact is complete - the ask never blocks the escalation.
 */
export function shouldShowAskForPerson({
  escalated,
  handoffSeen,
}: {
  escalated: boolean;
  handoffSeen: boolean;
}): boolean {
  return !escalated && !handoffSeen;
}
