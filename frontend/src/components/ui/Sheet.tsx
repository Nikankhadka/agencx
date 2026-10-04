"use client";

import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { useRestoreFocusTarget } from "@/lib/useRestoreFocusTarget";

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /**
   * `form` (default) caps at `max-w-md` at `lg+`, where every sheet becomes a
   * centered, height-capped dialog instead of a bottom pull-up. `document` is
   * the wider `--width-doc` (768px) for the knowledge review and the offering
   * detail. Below `lg` the variant changes nothing - both are bottom sheets.
   */
  variant?: "form" | "document";
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Overlay sheet (the "Sheet" half of the Modal/Sheet pair in design.md's
 * component wall). Below `lg` it is a mobile bottom sheet that slides up from
 * the bottom behind a scrim; at `lg+` the same panel becomes a centered,
 * height-capped dialog (`variant` picks `max-w-md` for forms or `--width-doc`
 * for document surfaces). Focus management matches Modal/Drawer: save active
 * element on open, focus the first focusable, restore on close, Escape/scrim
 * close, Tab wraps.
 *
 * Always rendered in the DOM (toggling `inert`), never conditionally
 * unmounted, so the slide transition has something to animate between.
 */
export function Sheet({ open, onClose, title, children, variant = "form" }: SheetProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const openerRef = useRestoreFocusTarget(panelRef);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current =
      openerRef.current ??
      (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    openerRef.current = null;
    const panel = panelRef.current;
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    (first ?? panel)?.focus();
    return () => {
      restoreFocusRef.current?.focus();
      restoreFocusRef.current = null;
    };
  }, [open, openerRef]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusables = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (!first || !last) {
      event.preventDefault();
      return;
    }
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === panel)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      inert={!open}
      aria-hidden={!open}
      onKeyDown={handleKeyDown}
      className="fixed inset-0 z-50 flex items-end justify-center lg:items-center lg:p-8"
    >
      <div
        aria-hidden="true"
        onClick={onClose}
        className={[
          "absolute inset-0 transition-colors duration-(--duration-push) ease-push",
          open ? "bg-scrim" : "pointer-events-none bg-transparent",
        ].join(" ")}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={[
          "absolute inset-x-0 bottom-0 flex max-h-[85%] flex-col rounded-t-3xl bg-surface p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-sheet",
          "lg:static lg:max-h-full lg:w-full lg:rounded-card",
          variant === "document" ? "lg:max-w-(--width-doc)" : "lg:max-w-md",
          "transition-transform duration-(--duration-push) ease-push",
          open
            ? "translate-y-0"
            : // The lg dialog is inset from the top as well as the bottom (the
              // root's `lg:p-8`) and capped at max-h-full, so translating by
              // its own height - the mobile behavior - stops its top short of
              // the viewport and leaves its header peeking above the fold. A
              // full viewport minus the 2rem top inset clears it at any panel
              // height.
              "translate-y-full lg:translate-y-[calc(100vh_-_2rem)]",
        ].join(" ")}
      >
        <div className="mx-auto mb-3 h-1 w-[42px] shrink-0 rounded-full bg-surface-container-high lg:hidden" />
        <div className="mb-3 flex shrink-0 items-center justify-between">
          <h2 id={titleId} className="text-title-3 font-semibold text-text">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-11 w-11 items-center justify-center rounded-full text-text-tertiary transition-colors duration-(--duration-fast) hover:bg-surface-container hover:text-text active:bg-surface-container-high"
          >
            <span aria-hidden="true" className="text-body-lg leading-none">
              ×
            </span>
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
