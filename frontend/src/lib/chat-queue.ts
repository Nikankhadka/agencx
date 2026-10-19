/**
 * A customer may keep typing and submitting while a reply is in flight. Those
 * questions wait here, in memory only, and are sent as one turn when the
 * current reply finishes. One coalesced turn measured 3.4-5.7 s against
 * 10.8-21.6 s for the same three questions sent serially (see
 * `docs/agencx/evidence/latency-2026-10/report-coalesce.md`).
 *
 * Pure functions so the trim/join rules are testable without a DOM: the repo
 * has no jsdom, and the component's only job is to hold the array.
 */

/** Append a submitted question, trimmed. Empty input is a no-op. */
export function enqueue(queue: readonly string[], text: string): string[] {
  const trimmed = text.trim();
  return trimmed ? [...queue, trimmed] : [...queue];
}

/** The one turn's payload: the queued questions in arrival order, blank-line separated. */
export function coalesce(queue: readonly string[]): string {
  return queue.join("\n\n");
}

/** Explicit empty queue for clearing after a drain or the customer's Clear control. */
export function clearQueue(): string[] {
  return [];
}

export function hasQueued(queue: readonly string[]): boolean {
  return queue.length > 0;
}

export function queuedCount(queue: readonly string[]): number {
  return queue.length;
}
