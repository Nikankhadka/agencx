"use client";

import { useEffect, useRef } from "react";

/** Roughly two seconds of frames - enough for a list query to resolve. */
const MAX_RESTORE_FRAMES = 120;

/**
 * RF-1: keep a scrollable element's position across a client-side navigation
 * away and back.
 *
 * Next.js restores the window's scroll on back/forward, but every console list
 * scrolls inside its own overflow container, and Next 16 only preserves those
 * DOM nodes (via React's `Activity`) when `cacheComponents` is enabled - which
 * this app does not turn on. So the one genuinely missing piece is the inner
 * container, and this is the smallest mechanism that supplies it: remember the
 * offset under a path key in `sessionStorage`, re-apply it on mount, and keep
 * re-applying while the list is still loading. No dependency, no global state.
 *
 * The scroll listener is the only writer. A cleanup write would be unsafe: by
 * the time an effect cleanup runs during navigation the node is already
 * detached and reads `scrollTop` 0, which would erase the saved offset.
 */
export function useScrollRestoration<T extends HTMLElement>(key: string) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const storageKey = `agencx:scroll:${key}`;
    let frame = 0;
    let target = 0;
    try {
      target = Number(window.sessionStorage.getItem(storageKey) ?? "0") || 0;
    } catch {
      target = 0;
    }

    const write = () => {
      frame = 0;
      if (!element.isConnected) return;
      try {
        window.sessionStorage.setItem(storageKey, String(element.scrollTop));
      } catch {
        // Private mode or a full quota: restoring scroll is a nicety, never a
        // correctness boundary, so a failed write must not break the screen.
      }
    };
    const onScroll = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(write);
    };
    element.addEventListener("scroll", onScroll, { passive: true });

    let frames = 0;
    const restore = () => {
      frame = 0;
      if (target <= 0) return;
      element.scrollTop = target;
      frames += 1;
      // The query resolves after mount, so keep applying the saved offset until
      // the list is tall enough to hold it (or the frame budget runs out).
      if (element.scrollTop >= target || frames >= MAX_RESTORE_FRAMES) return;
      frame = window.requestAnimationFrame(restore);
    };
    if (target > 0) frame = window.requestAnimationFrame(restore);

    return () => {
      element.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [key]);

  return ref;
}
