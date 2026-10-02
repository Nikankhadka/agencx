"use client";

import { useEffect, useRef, type RefObject } from "react";

/**
 * Remember the control that opened an overlay so focus can return to it on
 * close.
 *
 * Reading `document.activeElement` in the overlay's open effect is too late for
 * an always-mounted overlay (Sheet, Drawer): a child's `autoFocus` runs during
 * the commit, before passive effects, so the captured element is the overlay's
 * own input rather than the opener. Track every focus change on the page and
 * ignore the ones landing inside the overlay's own panel - those are the
 * overlay focusing itself, not the opener.
 *
 * A mount-on-open overlay (the ConfirmDialog's Modal) has no earlier focus
 * change to observe, so the consumer falls back to `document.activeElement` at
 * open time; this ref stays null in that case.
 */
export function useRestoreFocusTarget(panelRef: RefObject<HTMLElement | null>) {
  const target = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const onFocusIn = (event: FocusEvent) => {
      const node = event.target;
      if (!(node instanceof HTMLElement)) return;
      if (panelRef.current?.contains(node)) return;
      target.current = node;
    };
    document.addEventListener("focusin", onFocusIn);
    return () => document.removeEventListener("focusin", onFocusIn);
  }, [panelRef]);

  return target;
}
