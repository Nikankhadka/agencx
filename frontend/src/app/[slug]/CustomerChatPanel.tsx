"use client";

import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { DESKTOP_QUERY, useMediaQuery } from "@/lib/useMediaQuery";
import { useRestoreFocusTarget } from "@/lib/useRestoreFocusTarget";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface CustomerChatPanelProps {
  /** Whether the chat is presented. The panel itself decides how. */
  open: boolean;
  /** Hides the panel without unmounting its children (scrim, X, Escape). */
  onClose: () => void;
  /** The chat's accessible name: `aria-label` on the desktop panel,
   *  `aria-labelledby` on the mobile dialog. */
  title: string;
  children: ReactNode;
}

/**
 * RF-8: one chat host with two presentations. At `lg+` it is a docked,
 * non-modal right side panel: the page stays visible, scrollable and
 * interactive beside it (no scrim, no `aria-modal`, complementary landmark),
 * and the panel carries its own close control with focus moved in on open and
 * restored on close. Below `lg` it is the modal bottom sheet with a scrim,
 * focus trap, `aria-modal="true"`, and Escape/scrim close.
 *
 * One `CustomerChat` tree only. The children are rendered once inside the
 * always-mounted panel; the presentation is CSS (translation/position), an
 * animation class, and the ARIA/behaviour that must genuinely differ - never a
 * second conditional parent that would remount the thread on resize.
 */
export function CustomerChatPanel({
  open,
  onClose,
  title,
  children,
}: CustomerChatPanelProps) {
  const desktop = useMediaQuery(DESKTOP_QUERY);
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const openerRef = useRestoreFocusTarget(panelRef);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const scrollBeforeOpen = useRef<number | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current =
      openerRef.current ??
      (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    openerRef.current = null;
    const panel = panelRef.current;
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    if (desktop) {
      // Non-modal: move focus into the panel, but do not let the browser
      // scroll the page to bring the panel's first control into view.
      (first ?? panel)?.focus({ preventScroll: true });
    } else {
      // Modal sheet: remember the page's scroll position so closing it can
      // restore the customer's place. There is no scroll lock; the scrim sits
      // over the page.
      scrollBeforeOpen.current = window.scrollY;
      (first ?? panel)?.focus();
    }
    return () => {
      // Moving focus back to the opener can itself scroll the page; suppress
      // that so closing the sheet never resets the customer's position.
      restoreFocusRef.current?.focus({ preventScroll: true });
      restoreFocusRef.current = null;
      if (scrollBeforeOpen.current !== null) {
        const y = scrollBeforeOpen.current;
        scrollBeforeOpen.current = null;
        window.scrollTo(0, y);
      }
    };
  }, [open, desktop, openerRef]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || desktop) return;
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
      data-chat-host=""
      className={[
        // Closed: `fixed inset-0` so the panel can animate and stays out of
        // flow. Open mobile: the same viewport-covering container. Open
        // desktop: still fixed, but `pointer-events-none` lets the page behind
        // it be scrolled and clicked - only the panel itself is interactive.
        "fixed inset-0",
        open ? (desktop ? "pointer-events-none" : "z-50") : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {!desktop ? (
        <div
          aria-hidden="true"
          onClick={onClose}
          className={[
            "absolute inset-0 transition-colors duration-(--duration-push) ease-push",
            open ? "bg-scrim" : "pointer-events-none bg-transparent",
          ].join(" ")}
        />
      ) : null}
      <div
        ref={panelRef}
        {...(desktop
          ? { role: "complementary", "aria-label": title }
          : { role: "dialog", "aria-modal": true, "aria-labelledby": titleId })}
        tabIndex={-1}
        className={[
          "bg-surface",
          "flex flex-col p-4",
          desktop
            ? "pointer-events-auto absolute inset-y-0 right-0 z-50 w-(--width-panel) max-w-full transition-transform duration-(--duration-base) ease-out lg:border-l lg:border-hairline"
            : // Full viewport minus safe areas: the sheet fills the screen
              // (not the old 85% cap), so the composer is always reachable.
              "absolute inset-x-0 bottom-0 h-dvh rounded-t-3xl pb-[max(1rem,env(safe-area-inset-bottom))] shadow-sheet transition-transform duration-(--duration-push) ease-push",
          open
            ? "translate-x-0"
            : desktop
              ? "translate-x-full"
              : "-translate-y-full",
        ].join(" ")}
      >
        {desktop ? (
          <div className="mb-3 flex shrink-0 items-center justify-between border-b border-hairline pb-3">
            <h2 id={titleId} className="text-title-3 font-semibold text-text">
              {title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close chat"
              className="flex size-11 items-center justify-center rounded-full text-text-tertiary transition-colors duration-(--duration-fast) hover:bg-surface-container hover:text-text active:bg-surface-container-high"
            >
              <span aria-hidden="true" className="text-body-lg leading-none">
                ×
              </span>
            </button>
          </div>
        ) : (
          <>
            <div className="mx-auto mb-3 h-1 w-[42px] shrink-0 rounded-full bg-surface-container-high" />
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
          </>
        )}
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      </div>
    </div>
  );
}
