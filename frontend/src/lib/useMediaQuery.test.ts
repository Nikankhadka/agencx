import { describe, expect, it, vi } from "vitest";
import { subscribeToMediaQuery, type MediaQueryMatcher } from "./useMediaQuery";

/**
 * The repo has no jsdom/happy-dom (and adding one is out of scope), so the
 * hook's effect cannot be rendered here. The media-query wiring it depends on
 * is extracted as `subscribeToMediaQuery` precisely so it can be tested in
 * node with a mocked `matchMedia`; the E2E spec covers the live browser
 * behavior the hook produces.
 */
function fakeMatchMedia(initial: boolean) {
  const listeners = new Set<() => void>();
  const media: MediaQueryMatcher = {
    matches: initial,
    addEventListener: (_type, listener) => listeners.add(listener),
    removeEventListener: (_type, listener) => listeners.delete(listener),
  };
  return {
    media,
    setMatches(next: boolean) {
      media.matches = next;
      for (const listener of listeners) listener();
    },
    listenerCount: () => listeners.size,
  };
}

describe("subscribeToMediaQuery", () => {
  it("reports the current match on subscribe", () => {
    const { media } = fakeMatchMedia(true);
    const onChange = vi.fn();
    subscribeToMediaQuery(media, onChange);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("reports each change", () => {
    const { media, setMatches } = fakeMatchMedia(false);
    const onChange = vi.fn();
    subscribeToMediaQuery(media, onChange);

    setMatches(true);
    setMatches(false);

    expect(onChange.mock.calls).toEqual([[false], [true], [false]]);
  });

  it("unsubscribes so a change after teardown is ignored", () => {
    const { media, setMatches, listenerCount } = fakeMatchMedia(false);
    const onChange = vi.fn();
    const unsubscribe = subscribeToMediaQuery(media, onChange);
    expect(listenerCount()).toBe(1);

    unsubscribe();
    expect(listenerCount()).toBe(0);
    setMatches(true);
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});
