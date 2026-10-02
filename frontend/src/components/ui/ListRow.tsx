"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Icon } from "./Icon";

export interface ListRowProps {
  /** Identity (an initial or avatar) or icon slot at the start of the row. */
  leading?: ReactNode;
  /** The primary line. */
  title: ReactNode;
  /** One quiet line under the title - what the row currently holds. */
  meta?: ReactNode;
  /** The trailing action: a chevron, a status, a time, or controls. */
  trailing?: ReactNode;
  /** Unread activity: a bolder title plus a small accent dot by the name. */
  unread?: boolean;
  /** Where the row goes. Omitted, pass `onClick` - the row opens in place. */
  href?: string;
  onClick?: () => void;
  /** Layout only - padding, an accent wash, or a breakpoint visibility. */
  className?: string;
  testId?: string;
}

const ROW_CLASSES = "flex w-full items-center gap-4 text-left";

/**
 * RF-1: the console's one list-row grammar - an identity or icon slot, the
 * primary line, the meta line, and a trailing action. It replaces the rows
 * each screen used to hand-build (the Chats list, Home's waiting rows, the
 * knowledge records, the admin offering lists) and sits under `RowLink`, which
 * is the hub-screen spelling of the same grammar.
 *
 * The row is a link when it navigates, a button when it acts in place, and a
 * plain container when it only holds content (the admin rows whose trailing
 * slot carries the actual controls). The grammar owns the slot order, the
 * `flex items-center gap-4` layout, and the row type roles; each screen keeps
 * its own chrome - gutter, hairline, padding, hover - because a hub row, a
 * card row, and a guttered admin row sit in different containers. Baking one
 * set of chrome in would force callers to fight it with overrides, which
 * Tailwind does not resolve by source order.
 */
export function ListRow({
  leading,
  title,
  meta,
  trailing,
  unread = false,
  href,
  onClick,
  className = "",
  testId,
}: ListRowProps) {
  const classes = [ROW_CLASSES, className].filter(Boolean).join(" ");

  const inner = (
    <>
      {leading ? (
        <span data-slot="leading" className="flex shrink-0 items-center">
          {leading}
        </span>
      ) : null}
      <span data-slot="body" className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          {unread ? (
            <span
              data-testid="row-unread"
              aria-hidden="true"
              className="size-2 shrink-0 rounded-full bg-accent"
            />
          ) : null}
          <span
            data-slot="title"
            className={[
              "min-w-0 flex-1 truncate text-row-label text-text",
              unread ? "font-semibold" : "font-medium",
            ].join(" ")}
          >
            {title}
          </span>
        </span>
        {meta ? (
          <span data-slot="meta" className="mt-2 block text-meta text-ink-a40">
            {meta}
          </span>
        ) : null}
      </span>
      {trailing ? (
        <span data-slot="trailing" className="flex shrink-0 items-center gap-2">
          {trailing}
        </span>
      ) : null}
    </>
  );

  if (href) {
    return (
      <Link href={href} data-testid={testId} className={classes}>
        {inner}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} data-testid={testId} className={classes}>
        {inner}
      </button>
    );
  }
  return (
    <div data-testid={testId} className={classes}>
      {inner}
    </div>
  );
}

/**
 * The identity slot for a conversation row: the first letter of the customer's
 * name, or a conversation glyph when the row is identified by its reference
 * rather than a name. The letter tile is the same idiom the storefront already
 * uses for an offering with no image.
 */
export function RowIdentity({ label }: { label: string }) {
  const trimmed = label.trim();
  const initial = trimmed.charAt(0).toUpperCase() || "?";
  return (
    <span
      aria-hidden="true"
      className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-container text-body-sm font-semibold text-text-secondary"
    >
      {trimmed.startsWith("#") ? <Icon name="forum" size={16} /> : initial}
    </span>
  );
}
