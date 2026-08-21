"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Icon } from "./Icon";

export interface ScreenTopbarProps {
  title: string;
  /** Where back goes. Omit to pop the history stack (the prototype's navBack). */
  backHref?: string;
  /** Trailing slot - the prototype puts a close or an action glyph here. */
  action?: ReactNode;
}

/**
 * The prototype's `.dst-topbar`: a 58px bar with a back control, a centred-weight
 * title, and an optional trailing action, over a hairline rule. Every
 * destination screen in agencx-prototype-v6.html opens with this - it is what
 * makes a screen feel like a place you can leave, which matters most on a phone
 * where there is no sidebar to fall back to.
 */
export function ScreenTopbar({ title, backHref, action }: ScreenTopbarProps) {
  const router = useRouter();
  return (
    <header className="flex h-topbar shrink-0 items-center justify-between border-b border-hairline px-5 pb-3.5 pt-4">
      <button
        type="button"
        aria-label="Back"
        onClick={() => (backHref ? router.push(backHref) : router.back())}
        className="-ml-2 flex size-icon-btn items-center justify-center rounded-full text-text active:opacity-60"
      >
        <Icon name="arrow_back" size={20} />
      </button>
      <span className="text-screen-title font-medium text-text">{title}</span>
      <span className="flex size-icon-btn items-center justify-center">{action}</span>
    </header>
  );
}
