/**
 * C-6 Chats / home's waiting panel: the two bits of relative-time formatting
 * every screen showing a conversation stamp needs.
 *
 * Shared rather than duplicated per screen - a row saying "47m" next to a
 * panel saying "an hour ago" reads like two different systems.
 */

/** The prototype's relative stamps: `47m`, `2d`, `Yesterday`, `Mon`. */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const minutes = Math.max(0, Math.floor((now.getTime() - then.getTime()) / 60_000));
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return then.toLocaleDateString(undefined, { weekday: "short" });
  return then.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** The clock stamp beside a takeover/handback pill (the prototype's pillTime). */
export function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/**
 * A conversation's short reference: `#4F9A2C`, the head of its own uuid.
 *
 * The web chat surface never captures a name, so without this every row in the
 * owner's list is labelled identically and none of them can be pointed at. The
 * code is a literal prefix of the id in `/chats/<id>`, so a row and an open
 * thread cross-reference by eye - which is why it is derived rather than a
 * separate generated column nothing else would agree with.
 */
export function conversationRef(id: string): string {
  return `#${id.replace(/-/g, "").slice(0, 6).toUpperCase()}`;
}

/**
 * What every surface calls a conversation's customer: their name when they gave
 * one, the short reference when they did not. A name already identifies the row,
 * so it carries no code alongside it.
 */
export function customerLabel(customerRef: string | null | undefined, id: string): string {
  return customerRef?.trim() || conversationRef(id);
}
