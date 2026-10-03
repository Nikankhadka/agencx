"use client";

import { useEffect, useState } from "react";

/**
 * The desktop breakpoint (`lg` in Tailwind v4's default scale) the storefront
 * switches the chat presentation at. Owned here so the panel's presentation
 * (`CustomerChatPanel`) and the page's inset (`Storefront`) cannot drift.
 */
export const DESKTOP_QUERY = "(min-width: 1024px)";

/** The slice of `MediaQueryList` this module uses - enough to mock. */
export interface MediaQueryMatcher {
  matches: boolean;
  addEventListener: (type: "change", listener: () => void) => void;
  removeEventListener: (type: "change", listener: () => void) => void;
}

/**
 * Subscribe to a media query, calling `onChange` with the current match and
 * then on every change. Returns the unsubscribe function. Kept separate from
 * the hook so the wiring is unit-testable without a DOM (this repo has no
 * jsdom): the hook is a thin React wrapper over this.
 */
export function subscribeToMediaQuery<T extends MediaQueryMatcher>(
  media: T,
  onChange: (matches: boolean) => void,
): () => void {
  const update = () => onChange(media.matches);
  update();
  media.addEventListener("change", update);
  return () => media.removeEventListener("change", update);
}

/**
 * Track a CSS media query in React state. SSR-safe: the server (and the first
 * client render, before the effect runs) report `false`, so markup matches and
 * there is no hydration mismatch, then the subscription corrects it on mount.
 *
 * The one consumer is RF-8's chat presentation: the same `CustomerChat`
 * instance renders as a docked side panel at `lg+` and as the modal sheet
 * below it, so the component must know which side of the 1024px breakpoint it
 * is on. Deliberately not `matchMedia` at render time - that reads a browser
 * API during render, which is not allowed.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    return subscribeToMediaQuery(window.matchMedia(query), setMatches);
  }, [query]);

  return matches;
}
