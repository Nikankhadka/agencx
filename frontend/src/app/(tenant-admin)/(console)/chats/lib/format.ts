/**
 * C-6 Chats: the two bits of formatting both screens need.
 *
 * Kept out of the components because the list and the thread must agree - a
 * row saying "47m" next to a thread saying "an hour ago" reads like two
 * different systems.
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
